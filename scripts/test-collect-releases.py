#!/usr/bin/env python3
"""Check authenticated release collection without network access or real tokens."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import HTTPRedirectHandler


class CollectionTests(unittest.TestCase):
    def collect(self, environment):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            script = root / "scripts/collect-releases.py"
            shutil.copyfile(Path(__file__).with_name("collect-releases.py"), script)
            (root / "sources.json").write_text(json.dumps({"sources": [{
                "repository": "example/ui", "mode": "release", "series": "25.12",
                "architectures": ["noarch"], "assets": ["ui-*.apk"],
            }]}))
            package = b"fixture package"
            digest = hashlib.sha256(package).hexdigest()
            base = "https://github.com/example/ui/releases/download/v1/"
            release = {
                "tag_name": "v1", "html_url": base, "target_commitish": "fixture",
                "assets": [{"name": name, "browser_download_url": base + name}
                           for name in ("ui-1.apk", "ui-1.apk.sha256")],
            }
            replies = {
                "https://api.github.com/repos/example/ui/releases/latest": json.dumps(release).encode(),
                base + "ui-1.apk.sha256": f"{digest}  ui-1.apk\n".encode(),
                base + "ui-1.apk": package,
            }
            requests = []

            def response(request, timeout):
                requests.append(request)
                self.assertEqual(timeout, 90)
                return io.BytesIO(replies[request.full_url])

            with patch.dict("os.environ", environment, clear=True), patch(
                "sys.argv", [str(script), str(root / "collected/packages")]
            ), patch("urllib.request.urlopen", side_effect=response):
                runpy.run_path(str(script), run_name="__main__")
            self.assertEqual((root / "collected/packages/25.12/noarch/ui-1.apk").read_bytes(), package)
            provenance = json.loads((root / "collected/source-provenance.json").read_text())
            self.assertEqual(provenance["packages"][0]["sha256"], digest)
            self.assertEqual(len(requests), 3)
            for request in requests[1:]:
                self.assertIsNone(request.get_header("Authorization"), "asset requests must be anonymous")
            # urllib redirects copy regular headers, but not unredirected headers.
            redirected = HTTPRedirectHandler().redirect_request(
                requests[0], None, 302, "Found", {}, "https://release-assets.githubusercontent.com/fixture"
            )
            self.assertIsNone(redirected.get_header("Authorization"), "redirects must not carry API tokens")
            return requests[0].get_header("Authorization")

    def test_actions_token_authenticates_api_only(self):
        self.assertEqual(self.collect({"GH_TOKEN": "fixture-token"}), "Bearer fixture-token")

    def test_github_token_fallback(self):
        self.assertEqual(self.collect({"GITHUB_TOKEN": "fallback-token"}), "Bearer fallback-token")

    def test_local_collection_without_token(self):
        self.assertIsNone(self.collect({}))


if __name__ == "__main__":
    unittest.main()
