#!/usr/bin/env python3
"""Collect checksum-verified APKv3 files from standalone GitHub Releases.

No source checkout, code execution or package compilation happens here.
The central signing job is intentionally separate.
"""
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "packages"
MANIFEST = ROOT / "sources.json"
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SERIES = re.compile(r"^[0-9]+\.[0-9]+$")
ARCHITECTURE = re.compile(r"^[A-Za-z0-9_-]+$")
ASSET = re.compile(r"^[A-Za-z0-9._+~-]+\.apk$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_ASSET_BYTES = 100 * 1024 * 1024
HEADERS = {
    "User-Agent": "nieaowei-openwrt-apk-feed/1.0",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def download(url, max_bytes):
    # GitHub may redirect release assets to its download CDN.
    for attempt in range(3):
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=90) as response:
                chunks = []
                size = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"Asset exceeds {max_bytes} bytes: {url}")
                    chunks.append(chunk)
                return b"".join(chunks)
        except (HTTPError, URLError, TimeoutError) as e:
            if isinstance(e, HTTPError) and e.code in (401, 403, 404):
                raise RuntimeError(f"Cannot download {url} (HTTP {e.code})") from e
            if attempt == 2:
                raise
            print(f"Retrying {url}: {e}", flush=True)
            time.sleep(2 ** attempt)


def validate(text, pattern, what):
    if not isinstance(text, str) or not pattern.fullmatch(text):
        raise ValueError(f"Invalid {what}: {text!r}")
    return text


config = json.loads(MANIFEST.read_text(encoding="utf-8"))
sources = config.get("sources")
if not isinstance(sources, list) or not sources:
    raise ValueError("sources.json requires a nonempty sources array")
OUTPUT.mkdir(parents=True, exist_ok=True)
provenance = []

for source in sources:
    repo = validate(source["repository"], REPOSITORY, "repository")
    if source.get("mode") != "release":
        raise ValueError(f"{repo}: only mode=release is supported")
    series = validate(source["series"], SERIES, "OpenWrt release series")
    arches = source["architectures"]
    if not isinstance(arches, list) or not arches:
        raise ValueError(f"{repo}: architectures is empty")
    for arch in arches:
        validate(arch, ARCHITECTURE, "architecture")
    patterns = source.get("assets")
    if not isinstance(patterns, list) or not patterns or any(not isinstance(x, str) or
          not x.endswith(".apk") or "/" in x or "\\" in x for x in patterns):
        raise ValueError(f"{repo}: assets must be nonempty .apk glob patterns")

    release_name = source.get("release", "latest")
    if release_name == "latest":
        endpoint = f"https://api.github.com/repos/{repo}/releases/latest"
    elif isinstance(release_name, str) and re.fullmatch(r"[A-Za-z0-9._+~-]+", release_name):
        endpoint = f"https://api.github.com/repos/{repo}/releases/tags/{release_name}"
    else:
        raise ValueError(f"{repo}: invalid release tag: {release_name!r}")
    release = json.loads(download(endpoint, 4 * 1024 * 1024))
    if release.get("draft") or release.get("prerelease"):
        raise ValueError(f"{repo}: refusing draft/prerelease")
    assets = {item["name"]: item for item in release.get("assets", [])
              if isinstance(item.get("name"), str)}
    selected = sorted({name for name in assets
                       if ASSET.fullmatch(name) and any(fnmatch.fnmatchcase(name, p) for p in patterns)})
    if not selected:
        raise ValueError(f"{repo} {release.get('tag_name')}: no matching APK assets: {patterns}")
    for pattern in patterns:
        if not any(fnmatch.fnmatchcase(name, pattern) for name in selected):
            raise ValueError(f"{repo}: no APK matches {pattern}")

    print(f"Collecting {repo} release {release['tag_name']} ({len(selected)} APK)", flush=True)
    for name in selected:
        checksum_name = name + ".sha256"
        if checksum_name not in assets:
            raise ValueError(f"{repo}: missing checksum asset {checksum_name}")
        expected_text = download(assets[checksum_name]["browser_download_url"], 4096).decode("utf-8")
        hashes = {}
        for line in expected_text.splitlines():
            match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](\S+)", line.strip())
            if match:
                hashes[match.group(2)] = match.group(1).lower()
        expected = hashes.get(name)
        if not expected or not SHA256.fullmatch(expected):
            raise ValueError(f"{repo}: invalid SHA256 file for {name}")
        package = download(assets[name]["browser_download_url"], MAX_ASSET_BYTES)
        actual = hashlib.sha256(package).hexdigest()
        if actual != expected:
            raise ValueError(f"{repo}: hash mismatch for {name}, expected {expected}, got {actual}")
        for arch in arches:
            destination = OUTPUT / series / arch / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError(f"Duplicate package: {destination}")
            destination.write_bytes(package)
            print(f"Verified sha256 {actual}: {destination}", flush=True)
        provenance.append({
            "repository": repo, "release": release["tag_name"],
            "release_url": release["html_url"], "package": name,
            "sha256": actual, "series": series, "architectures": arches,
            "source_commit": release.get("target_commitish", ""),
        })

# This file is published as provenance metadata by the Pages deployment.
(OUTPUT.parent / "source-provenance.json").write_text(
    json.dumps({"packages": provenance}, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print(f"Collected {len(provenance)} verified APK release asset(s)", flush=True)
