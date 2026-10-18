"""AUR snapshots, local overlays, and publication of supporting-file updates."""

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import far
import far_aur


def sources(version="1.0", content=b"fixture source\n"):
    digest = hashlib.sha256(content).hexdigest()
    return {"PKGBUILD": (
        f"pkgname=fixture\npkgver={version}\npkgrel=1\nepoch=1\n"
        "pkgdesc='Metadata test fixture'\narch=('x86_64' 'aarch64')\n"
        f"source=('asset.txt')\nsha256sums=('{digest}')\n"
        'package() { install -Dm644 "$srcdir/asset.txt" "$pkgdir/usr/share/fixture/asset.txt"; }\n'
    ).encode(), "asset.txt": content}


class SnapshotPolicyTests(unittest.TestCase):
    def test_source_paths_cannot_escape_or_replace_automation(self):
        for name in ("../outside", "/tmp/outside", "keys/../../outside", ".git/config", "far.patch",
                     "README.md", "AGENTS.md", "update.py", ".nvchecker.toml", ".aur.json",
                     "a\nb", "folder//file", "download.AppImage", "app.pkg.tar.zst"):
            with self.subTest(name=name):
                self.assertFalse(far_aur.source_path(name))
        for name in ("PKGBUILD", ".SRCINFO", "spotify.sh", "keys/pgp/ABC.asc", "0001-fix.patch"):
            self.assertTrue(far_aur.source_path(name), name)

    def test_arch_versions_preserve_epochs_build_dates_and_pkgrel(self):
        self.assertEqual(far_aur.metadata_version("\tpkgver = 1.2.0_2026.10.14\n\tpkgrel = 1.1\n"),
                         "1.2.0_2026.10.14-1.1")
        self.assertEqual(far_aur.metadata_version("\tpkgver = 1.3.4.258\n\tpkgrel = 2\n\tepoch = 1\n"),
                         "1:1.3.4.258-2")


@unittest.skipUnless(shutil.which("makepkg") and shutil.which("shellcheck"), "requires Arch metadata tools")
class AurUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="far-aur-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name) / "fixture"
        self.package.mkdir()
        (self.package / "README.md").write_text("Fixture documentation\n")
        (self.package / ".nvchecker.toml").write_text('[fixture]\nsource="aur"\naur="fixture"\n')
        far_aur.prepare_snapshot(self.package, "1" * 40, sources(), None)

    def test_same_revision_is_noop_and_modified_local_files_are_rejected(self):
        with patch.object(far_aur, "fetch_snapshot", return_value=("1" * 40, sources())):
            self.assertEqual(far.update_one(self.package, apply=True)["status"], "up-to-date")
        (self.package / "asset.txt").write_text("unexpected local modification")
        with self.assertRaisesRegex(far.MaintenanceError, "differs from"):
            far.update_one(self.package)

    def test_new_snapshot_updates_support_files_and_metadata(self):
        new_sources = sources("1.1", b"new content\n") | {"new-file.txt": b"new support file\n"}
        with patch.object(far_aur, "fetch_snapshot", return_value=("2" * 40, new_sources)):
            preview = far.update_one(self.package)
            self.assertEqual(preview["status"], "available")
            self.assertEqual(far_aur.read_manifest(self.package)["revision"], "1" * 40)
            applied = far.update_one(self.package, apply=True)
        self.assertEqual(applied["version"], "1:1.1-1")
        self.assertEqual((self.package / "new-file.txt").read_bytes(), b"new support file\n")
        far.check_package(self.package)

    def test_removes_obsolete_support_files_and_accepts_same_version_recipe_fixes(self):
        new_sources = sources() | {"replacement.txt": b"replacement\n"}
        new_sources.pop("asset.txt")
        # Change the local source name and leave the software version unchanged.
        new_sources["PKGBUILD"] = new_sources["PKGBUILD"].replace(b"asset.txt", b"replacement.txt")
        with patch.object(far_aur, "fetch_snapshot", return_value=("2" * 40, new_sources)):
            report = far.update_one(self.package, apply=True)
        self.assertEqual(report["old_version"], report["version"])
        self.assertIn("asset.txt", report["removed_files"])
        self.assertFalse((self.package / "asset.txt").exists())

    def test_downgrade_and_overlay_conflict_leave_package_untouched(self):
        original = far_aur.read_manifest(self.package)
        with patch.object(far_aur, "fetch_snapshot", return_value=("2" * 40, sources("0.9"))):
            with self.assertRaisesRegex(far.MaintenanceError, "downgrade"):
                far.update_one(self.package, apply=True)
        overlay = self.package / "far.patch"
        overlay.write_text("--- a/PKGBUILD\n+++ b/PKGBUILD\n@@ -1 +1 @@\n-missing-line\n+changed-line\n")
        with patch.object(far_aur, "fetch_snapshot", return_value=("2" * 40, sources("1.1"))):
            with self.assertRaisesRegex(far.MaintenanceError, "git failed"):
                far.update_one(self.package, apply=True)
        self.assertEqual(far_aur.read_manifest(self.package), original)
        far_aur.verify_manifest(self.package)

    def test_overlay_is_reapplied_to_new_snapshot(self):
        (self.package / "far.patch").write_text(
            "--- a/PKGBUILD\n+++ b/PKGBUILD\n@@ -3,2 +3,3 @@\n pkgrel=1\n+# Persistent local policy\n epoch=1\n")
        with patch.object(far_aur, "fetch_snapshot", return_value=("2" * 40, sources("1.1"))):
            far.update_one(self.package, apply=True)
        self.assertIn("# Persistent local policy", (self.package / "PKGBUILD").read_text())
        far_aur.verify_manifest(self.package)

    def test_failed_final_validation_restores_added_and_removed_files(self):
        original = far_aur.read_manifest(self.package)
        new_sources = sources("1.1") | {"new-file.txt": b"new\n"}
        with patch.object(far_aur, "fetch_snapshot", return_value=("2" * 40, new_sources)), \
                patch.object(far_aur, "check_package", side_effect=[None, far.MaintenanceError("failure")]):
            with self.assertRaisesRegex(far.MaintenanceError, "failure"):
                far.update_one(self.package, apply=True)
        self.assertFalse((self.package / "new-file.txt").exists())
        self.assertEqual(far_aur.read_manifest(self.package), original)
        far_aur.verify_manifest(self.package)


if __name__ == "__main__":
    unittest.main()
