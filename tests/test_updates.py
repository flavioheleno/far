"""Selection and integrity regressions; these tests never build a package."""

import hashlib
import io
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import far  # noqa: E402

PACKAGE = ROOT / "packages" / "bambustudio-appimage"
CONFIG = far.read_config(PACKAGE)
SELECT = runpy.run_path(str(PACKAGE / "update.py"))["select_candidate"]
PAYLOAD = b"fixture AppImage bytes; never executed"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def release(tag="v02.08.05.01", *, beta=True, variant="ubu24", stamp="20261017123456"):
    name = f"BambuStudio_{variant}-{tag}-{stamp}.AppImage"
    return {"tag_name": tag, "draft": False, "prerelease": beta,
            "assets": [{"name": name, "state": "uploaded", "size": len(PAYLOAD),
                        "digest": f"sha256:{DIGEST}",
                        "browser_download_url": f"https://github.com/bambulab/BambuStudio/releases/download/{tag}/{name}"}]}


class SelectionTests(unittest.TestCase):
    def test_selects_highest_version_not_api_order_or_publication_order(self):
        releases = [release("v02.08.03.99"), release("v02.08.05.01"), release("v02.08.04.99")]
        self.assertEqual(SELECT(releases, CONFIG)["version"], "2.8.5.1")

    def test_stable_channel_excludes_beta_and_all_channels_exclude_drafts(self):
        draft = release("v99.00.00.01")
        draft["draft"] = True
        releases = [draft, release(), release("v02.08.02.61", beta=False)]
        self.assertEqual(SELECT(releases, CONFIG)["version"], "2.8.5.1")
        self.assertEqual(SELECT(releases, CONFIG | {"include_prereleases": False})["version"], "2.8.2.61")

    def test_full_build_component_is_preserved(self):
        self.assertGreater(far.version_key("2.8.4.61"), far.version_key("2.8.4.57"))
        self.assertEqual(far.normalize_tag("v02.08.04.57", CONFIG), "2.8.4.57")

    def test_known_ubuntu24_names_are_supported(self):
        for variant in ("ubu24", "ubuntu24.04", "ubuntu-24.04"):
            with self.subTest(variant=variant):
                self.assertIn(variant, SELECT([release(variant=variant)], CONFIG)["asset"])

    def test_latest_release_without_target_asset_fails_instead_of_falling_back(self):
        with self.assertRaisesRegex(far.MaintenanceError, "found 0"):
            SELECT([release(variant="ubu22"), release("v02.08.04.57")], CONFIG)

    def test_other_architecture_and_wrong_tag_assets_are_rejected(self):
        for name in ("BambuStudio_ubu24-v02.08.05.01-20261017123456-aarch64.AppImage",
                     "BambuStudio_ubu24-v02.08.04.57-20261017123456.AppImage"):
            data = release()
            data["assets"][0]["name"] = name
            with self.assertRaisesRegex(far.MaintenanceError, "found 0"):
                SELECT([data], CONFIG)

    def test_multiple_target_assets_require_review(self):
        data = release()
        data["assets"].extend(release(stamp="20261017123457")["assets"])
        with self.assertRaisesRegex(far.MaintenanceError, "found 2"):
            SELECT([data], CONFIG)

    def test_asset_url_state_size_and_digest_are_validated(self):
        cases = [("browser_download_url", "https://example.org/asset.AppImage"),
                 ("state", "starter"), ("size", 0), ("size", True), ("digest", "sha256:bad")]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = release()
                data["assets"][0][field] = value
                with self.assertRaises(far.MaintenanceError):
                    SELECT([data], CONFIG)

    def test_package_discovery_rejects_unknown_and_traversal_names(self):
        for name in ("../bambustudio-appimage", "missing", "bambustudio-appimage/PKGBUILD"):
            with self.assertRaises(far.MaintenanceError):
                far.package_paths([name])


class IntegrityTests(unittest.TestCase):
    def test_streamed_digest_matches_published_digest(self):
        candidate = SELECT([release()], CONFIG)
        with patch.object(far, "urlopen", return_value=io.BytesIO(PAYLOAD)) as request:
            self.assertEqual(far.download_hash(candidate), DIGEST)
        self.assertNotIn("Authorization", request.call_args.args[0].headers)

    def test_digest_mismatch_and_truncated_download_fail(self):
        candidate = SELECT([release()], CONFIG)
        for payload in (b"x" * len(PAYLOAD), PAYLOAD[:-1], PAYLOAD + b"x"):
            with self.subTest(payload=payload):
                with patch.object(far, "urlopen", return_value=io.BytesIO(payload)):
                    with self.assertRaises(far.MaintenanceError):
                        far.download_hash(candidate)

    def test_asset_without_digest_is_hashed(self):
        candidate = SELECT([release()], CONFIG) | {"sha256": None}
        with patch.object(far, "urlopen", return_value=io.BytesIO(PAYLOAD)):
            self.assertEqual(far.download_hash(candidate), DIGEST)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name) / PACKAGE.name
        shutil.copytree(PACKAGE, self.package, ignore=shutil.ignore_patterns("__pycache__"))
        self.original = (self.package / "PKGBUILD").read_text()
        self.srcinfo = (self.package / ".SRCINFO").read_bytes()

    def current_release(self):
        data = release("v02.08.04.57", stamp="20260922164607")
        data["assets"][0]["digest"] = "sha256:" + far.source_hash(self.original)
        return data

    def test_current_recipe_is_noop_without_download(self):
        with patch.object(far, "download_hash") as download:
            result = far.update_one(self.package, [self.current_release()], apply=True)
        self.assertEqual(result["status"], "up-to-date")
        download.assert_not_called()
        self.assertEqual((self.package / "PKGBUILD").read_text(), self.original)

    def test_republished_content_or_filename_requires_manual_review(self):
        for mutate in (lambda data: data["assets"][0].update(digest="sha256:" + DIGEST),
                       lambda data: data["assets"][0].update(name=data["assets"][0]["name"].replace("164607", "164608"))):
            data = self.current_release()
            mutate(data)
            # Ensure renamed assets still have a valid, matching URL.
            data["assets"][0]["browser_download_url"] = (
                f"https://github.com/bambulab/BambuStudio/releases/download/{data['tag_name']}/{data['assets'][0]['name']}")
            with self.assertRaisesRegex(far.MaintenanceError, "unchanged version"):
                far.update_one(self.package, [data], apply=True)

    def test_downgrade_is_rejected(self):
        with self.assertRaisesRegex(far.MaintenanceError, "downgrade"):
            far.update_one(self.package, [release("v02.08.02.61", beta=False)], apply=True)

    def test_preview_checks_download_without_modifying_recipe(self):
        with patch.object(far, "download_hash", return_value=DIGEST):
            result = far.update_one(self.package, [release()])
        self.assertEqual(result["status"], "available")
        self.assertEqual((self.package / "PKGBUILD").read_text(), self.original)

    def test_apply_updates_metadata_resets_pkgrel_and_is_idempotent(self):
        path = self.package / "PKGBUILD"
        path.write_text(self.original.replace("pkgrel=1", "pkgrel=8"))
        with patch.object(far, "download_hash", return_value=DIGEST), \
                patch.object(far, "generate_srcinfo", return_value="generated metadata\n"), \
                patch.object(far, "check_package"):
            result = far.update_one(self.package, [release()], apply=True)
            again = far.update_one(self.package, [release()], apply=True)
        self.assertEqual(result["status"], "updated")
        self.assertEqual(again["status"], "up-to-date")
        self.assertEqual(far.assignment(path.read_text(), "pkgrel"), "1")
        self.assertEqual(far.assignment(path.read_text(), "pkgver"), "2.8.5.1")
        self.assertEqual(far.source_hash(path.read_text()), DIGEST)
        self.assertEqual((self.package / ".SRCINFO").read_text(), "generated metadata\n")

    def test_metadata_or_validation_failure_restores_both_files(self):
        for failure in ("generate_srcinfo", "check_package"):
            with self.subTest(failure=failure):
                with patch.object(far, "download_hash", return_value=DIGEST), \
                        patch.object(far, "generate_srcinfo", return_value="new metadata\n"), \
                        patch.object(far, "check_package"), \
                        patch.object(far, failure, side_effect=far.MaintenanceError("fixture failure")):
                    with self.assertRaisesRegex(far.MaintenanceError, "fixture failure"):
                        far.update_one(self.package, [release()], apply=True)
                self.assertEqual((self.package / "PKGBUILD").read_text(), self.original)
                self.assertEqual((self.package / ".SRCINFO").read_bytes(), self.srcinfo)

    def test_makepkg_receives_no_automation_credentials(self):
        completed = subprocess.CompletedProcess([], 0, stdout=f"pkgbase = {PACKAGE.name}\n", stderr="")
        with patch.dict(far.os.environ, {"GH_TOKEN": "fixture", "GITHUB_TOKEN": "fixture", "PRIVATE_KEY": "fixture"}), \
                patch.object(far.subprocess, "run", return_value=completed) as run:
            far.generate_srcinfo(self.package)
        env = run.call_args.kwargs["env"]
        self.assertFalse({"GH_TOKEN", "GITHUB_TOKEN", "PRIVATE_KEY"} & env.keys())


if __name__ == "__main__":
    unittest.main()
