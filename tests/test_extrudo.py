"""Stable Extrudo asset selection and exact requested source integrity."""

from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import far

PACKAGE = ROOT / "packages/extrudo-appimage"
CONFIG = far.read_config(PACKAGE)
ADAPTER = runpy.run_path(str(PACKAGE / "update.py"))
DIGEST = "1b661cfcbfe92c16bf9ab5c109a1fe8c7e9a59e122c71d1b2e4ba724689b7f9d"


def release(version="0.7.0", beta=False):
    name = f"extrudo-{version}-linux-x86_64.AppImage"
    return {"tag_name": f"v{version}", "draft": False, "prerelease": beta,
            "assets": [{"name": name, "state": "uploaded", "size": 140308968,
                        "digest": f"sha256:{DIGEST}",
                        "browser_download_url": f"https://github.com/zoltanf/extrudo/releases/download/v{version}/{name}"}]}


class ExtrudoTests(unittest.TestCase):
    def test_requested_initial_asset_and_checksum_are_exact(self):
        candidate = ADAPTER["select_candidate"]([release()], CONFIG)
        self.assertEqual(candidate["version"], "0.7.0")
        self.assertEqual(candidate["sha256"], DIGEST)
        self.assertEqual(far.source_hash((PACKAGE / "PKGBUILD").read_text()), DIGEST)

    def test_stable_selection_ignores_beta_and_api_order(self):
        candidate = ADAPTER["select_candidate"]([release("1.0.0", beta=True), release(), release("0.8.0")], CONFIG)
        self.assertEqual(candidate["version"], "0.8.0")

    def test_missing_duplicate_and_wrong_architecture_assets_fail(self):
        for assets in ([], release()["assets"] * 2,
                       [release()["assets"][0] | {"name": "extrudo-0.7.0-linux-aarch64.AppImage"}]):
            with self.assertRaises(far.MaintenanceError):
                ADAPTER["select_candidate"]([release() | {"assets": assets}], CONFIG)

    def test_foreign_download_url_is_rejected(self):
        data = release()
        data["assets"][0]["browser_download_url"] = "https://example.org/extrudo.AppImage"
        with self.assertRaises(far.MaintenanceError):
            ADAPTER["select_candidate"]([data], CONFIG)


if __name__ == "__main__":
    unittest.main()
