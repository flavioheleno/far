"""Direct upstream integrity checks; no network or package builds."""

import hashlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import far
import far_upstream as upstream
import upstreams

CONFIG = {"source": "upstream", "mode": "debian", "hosts": ["vendor.example"],
          "assignments": ["pkgver", "_url"],
          "sources": [{"variable": "_url", "array": "sha256sums", "index": 0, "algorithm": "sha256"}]}
PAYLOAD = b"fixture payload"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
RECIPE = "pkgver=1.0\npkgrel=4\n_url='https://vendor.example/1.0.deb'\nsha256sums=('" + "0" * 64 + "'\n '" + "1" * 64 + "')\n"


def candidate():
    return {"version": "1.1", "release_url": "https://vendor.example/releases", "prerelease": False,
            "assignments": {"pkgver": "1.1", "_url": "https://vendor.example/1.1.deb"},
            "sources": [CONFIG["sources"][0] | {"url": "https://vendor.example/1.1.deb",
                         "size": len(PAYLOAD), "digest": DIGEST, "checksum": DIGEST}]}


class IntegrityTests(unittest.TestCase):
    def test_source_mapping_and_urls_cannot_escape_configuration(self):
        upstream.validate_config(CONFIG)
        upstream.validate_candidate(candidate(), CONFIG)
        for change in ({"url": "http://vendor.example/1.1.deb"}, {"array": "sha512sums"},
                       {"size": True}, {"digest": "bad"}, {"url": "https://other.example/payload"}):
            data = candidate()
            data["sources"][0].update(change)
            with self.assertRaises(far.MaintenanceError):
                upstream.validate_candidate(data, CONFIG)

    def test_hashes_streams_and_rejects_corrupt_or_truncated_payloads(self):
        for payload in (PAYLOAD, PAYLOAD[:-1], PAYLOAD + b"x", b"x" * len(PAYLOAD)):
            with patch.object(upstream, "open_upstream", return_value=io.BytesIO(payload)):
                if payload == PAYLOAD:
                    self.assertEqual(upstream.hash_source(candidate()["sources"][0], CONFIG), DIGEST)
                else:
                    with self.assertRaises(far.MaintenanceError):
                        upstream.hash_source(candidate()["sources"][0], CONFIG)

    def test_updates_one_checksum_and_preserves_supporting_file_checksums(self):
        rendered = upstream.render_recipe(RECIPE, candidate())
        self.assertEqual(upstream.checksum_values(rendered, "sha256sums"), [DIGEST, "1" * 64])
        self.assertEqual(far.assignment(rendered, "pkgver"), "1.1")
        self.assertEqual(far.assignment(rendered, "pkgrel"), "1")

    def test_publication_checks_literals_without_executing_recipe(self):
        rendered = upstream.render_recipe(RECIPE, candidate())
        report = candidate() | {"old_version": "1.0"}
        with patch.object(far, "generate_srcinfo", side_effect=AssertionError("executed recipe")):
            body = upstream.publication_body(Path("fixture"), rendered, report, CONFIG)
        self.assertIn(DIGEST, body)
        report["sources"][0]["checksum"] = "f" * 64
        with self.assertRaises(far.MaintenanceError):
            upstream.publication_body(Path("fixture"), rendered, report, CONFIG)

    def test_arch_version_comparison_preserves_dated_builds(self):
        self.assertGreater(upstream.compare_versions("1.2.0_2026.10.21", "1.2.0_2026.10.14"), 0)
        self.assertLess(upstream.compare_versions("1.0", "2.0"), 0)


class GithubDiscoveryTests(unittest.TestCase):
    def config(self, name):
        return far.read_config(Path(__file__).resolve().parents[1] / "packages" / name)

    def release(self, config, tag):
        return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [
            {"name": entry["asset"], "size": len(PAYLOAD), "digest": "sha256:" + DIGEST,
             "state": "uploaded", "browser_download_url":
             f"https://github.com/{config['github']}/releases/download/{tag}/{entry['asset']}"}
            for entry in config["sources"] if "asset" in entry]}

    def test_rtk_and_tailwind_include_both_architectures_and_release_license(self):
        for name in ("rtk-bin", "tailwindcss-bin"):
            config = self.config(name)
            data = self.release(config, "v99.1.0")
            with patch.object(upstreams, "github_releases", return_value=[data]):
                selected = upstreams.github_assets(config)
            upstream.validate_candidate(selected, config)
            self.assertEqual(selected["version"], "99.1.0")
            self.assertEqual(len(selected["sources"]), 3)
            self.assertIn("/raw/v99.1.0/LICENSE", selected["assignments"]["_url_license"])
            data["assets"].pop()
            with patch.object(upstreams, "github_releases", return_value=[data]):
                with self.assertRaisesRegex(far.MaintenanceError, "found 0"):
                    upstreams.github_assets(config)

    def test_newest_missing_asset_does_not_fall_back_to_an_older_release(self):
        config = self.config("rtk-bin")
        newest = self.release(config, "v99.1.0")
        newest["assets"] = []
        with patch.object(upstreams, "github_releases", return_value=[newest, self.release(config, "v1.0.0")]):
            with self.assertRaises(far.MaintenanceError):
                upstreams.github_assets(config)

    def test_freecad_uses_tagged_version_json_and_complete_weekly_date(self):
        config = self.config("freecad-weekly-appimage")
        tag = "weekly-2026.10.21"
        name = f"FreeCAD_{tag}-Linux-x86_64.AppImage"
        data = {"tag_name": tag, "prerelease": True, "draft": False, "assets": [
            {"name": name, "size": 100, "digest": "sha256:" + DIGEST, "state": "uploaded",
             "browser_download_url": f"https://github.com/FreeCAD/FreeCAD/releases/download/{tag}/{name}"}]}
        recipe = "pkgver=1.2.0_2026.10.14\n_upstream_tag='weekly-2026.10.14'\n"
        with patch.object(upstreams, "github_releases", return_value=[data]), \
                patch.object(upstreams, "fetch", return_value=b'{"version_major":1,"version_minor":2,"version_patch":0}') as fetch:
            selected = upstreams.freecad_weekly(config, recipe)
        upstream.validate_candidate(selected, config)
        self.assertEqual(selected["version"], "1.2.0_2026.10.21")
        self.assertIn(f"/{tag}/version.json", fetch.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
