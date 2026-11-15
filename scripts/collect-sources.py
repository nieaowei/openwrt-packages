#!/usr/bin/env python3
"""Build APKs from independently maintained source repositories.

This stage is intentionally separate from signing: source build scripts never
receive the APK signing key or access to the GitHub Pages deployment token.
"""
import glob
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "sources.json"
OUTPUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "packages"
NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF = re.compile(r"^[A-Za-z0-9_./-]+$")
ARCH = re.compile(r"^[A-Za-z0-9_]+$")
SERIES = re.compile(r"^\d+\.\d+$")
SCRIPT = re.compile(r"^[A-Za-z0-9_./-]+$")
GLOB = re.compile(r"^[A-Za-z0-9_.*?/-]+$")


def require(value, pattern, what):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"Invalid {what}: {value!r}")
    if value.startswith(("/", "-")) or ".." in value.split("/"):
        raise ValueError(f"Unsafe {what}: {value!r}")
    return value


def run(args, cwd=None, env=None):
    print("+ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True, timeout=1200)


sources = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]
if not isinstance(sources, list) or not sources:
    raise ValueError("sources.json must contain a nonempty sources array")
OUTPUT.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="openwrt-sources-") as scratch:
    for i, source in enumerate(sources):
        repo = require(source["repository"], NAME, "repository")
        ref = require(source.get("ref", "main"), REF, "ref")
        mode = source.get("mode", "build")
        if mode != "build":
            raise ValueError(f"Only source build mode is currently supported: {repo}")
        script = require(source["script"], SCRIPT, "script")
        artifact_glob = require(source.get("artifact_glob", "dist/*.apk"), GLOB, "artifact_glob")
        series = require(source["series"], SERIES, "series")
        architectures = source["architectures"]
        if not isinstance(architectures, list) or not architectures:
            raise ValueError(f"No architectures set for {repo}")
        for arch in architectures:
            require(arch, ARCH, "architecture")

        clone = Path(scratch) / f"source-{i}"
        if re.fullmatch(r"[0-9a-fA-F]{40}", ref):
            run(["git", "clone", "--no-checkout", "https://github.com/" + repo + ".git", str(clone)])
            run(["git", "checkout", "--detach", ref], cwd=clone)
        else:
            run(["git", "clone", "--depth=1", "--branch", ref, "https://github.com/" + repo + ".git", str(clone)])
        run(["git", "rev-parse", "HEAD"], cwd=clone)

        build_script = (clone / script).resolve()
        if not build_script.is_file() or not build_script.is_relative_to(clone):
            raise ValueError(f"Missing or unsafe build script {script} in {repo}")
        env = os.environ.copy()
        # The upstream build-apk.sh uses a Docker image pinned by digest.
        run(["sh", script], cwd=clone, env=env)
        matches = sorted(Path(p).resolve() for p in glob.glob(str(clone / artifact_glob)))
        if not matches:
            raise ValueError(f"No APK artifacts produced by {repo}: {artifact_glob}")
        for apk in matches:
            if not apk.is_file() or not apk.is_relative_to(clone) or apk.suffix != ".apk":
                raise ValueError(f"Unexpected artifact from {repo}: {apk}")
            for arch in architectures:
                dest = OUTPUT / series / arch / apk.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    raise FileExistsError(f"Duplicate package artifact: {dest}")
                shutil.copy2(apk, dest)
                print(f"Collected {repo} -> {dest}", flush=True)
