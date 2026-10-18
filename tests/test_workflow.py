"""Exercise the text-only boundary between update preparation and publication."""

import base64
import json
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
import far
import workflow
import far_aur
from test_aur import sources
from test_updates import CONFIG, DIGEST, release


class PayloadTests(unittest.TestCase):
    def test_invalid_and_oversized_payloads_are_rejected(self):
        for value in ("", "not base64!", base64.b64encode(b"x" * (workflow.LIMIT + 1)).decode()):
            with self.subTest(value=value[:20]):
                with self.assertRaises((far.MaintenanceError, ValueError)):
                    workflow.decode(value)

    def test_workflow_outputs_reject_newline_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(far.MaintenanceError):
                workflow.write_outputs(Path(directory) / "outputs", {"title": "update\npatch=evil"})


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.package = self.root / "packages" / "bambustudio-appimage"
        shutil.copytree(ROOT / "packages" / self.package.name, self.package,
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "README.md").write_text("fixture documentation\n")
        (self.root / ".gitignore").write_text("__pycache__/\n")
        self.run_git("init", "-q")
        self.run_git("add", ".")
        self.run_git("-c", "user.name=FAR tests", "-c", "user.email=far@example.invalid", "commit", "-qm", "fixture")
        self.root_patch = patch.object(workflow, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def run_git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True).stdout

    def update_patch(self):
        recipe = self.package / "PKGBUILD"
        original = recipe.read_text()
        adapter = runpy.run_path(str(self.package / "update.py"))
        candidate = adapter["select_candidate"]([release()], CONFIG)
        recipe.write_text(adapter["render_recipe"](original, candidate))
        metadata = self.package / ".SRCINFO"
        metadata.write_text(metadata.read_text().replace("2.8.4.57", "2.8.5.1"))
        payload = self.run_git("diff", "--no-ext-diff", "--no-textconv")
        # Restore the fixture without reset/checkout commands or changing history.
        for file in (recipe, metadata):
            file.write_bytes(self.run_git("show", "HEAD:" + file.relative_to(self.root).as_posix()))
        report = {"package": self.package.name, "status": "updated", "old_version": "2.8.4.57",
                  "version": candidate["version"], "sha256": DIGEST,
                  "asset": candidate["asset"], "release_url": candidate["release_url"], "prerelease": True}
        return payload, report

    def test_checked_patch_round_trips_without_executing_the_recipe(self):
        payload, report = self.update_patch()
        with patch.object(far, "generate_srcinfo", side_effect=AssertionError("recipe evaluated")), \
                patch.object(workflow, "check_package", side_effect=AssertionError("recipe evaluated")):
            outputs = workflow.apply_payload(self.package, payload, report, self.root / "body.md")
        self.assertIn("2.8.5.1", outputs["title"])
        self.assertEqual(far.assignment((self.package / "PKGBUILD").read_text(), "pkgver"), "2.8.5.1")
        self.assertIn("No package was built or uploaded", (self.root / "body.md").read_text())

    def test_patch_touching_other_files_is_rejected_before_applying(self):
        payload, report = self.update_patch()
        readme = self.root / "README.md"
        readme.write_text("unexpected change\n")
        unrelated = self.run_git("diff")
        readme.write_text("fixture documentation\n")
        with self.assertRaisesRegex(far.MaintenanceError, "only the selected"):
            workflow.apply_payload(self.package, payload + unrelated, report, self.root / "body.md")
        self.assertEqual(self.run_git("diff"), b"")

    def test_report_for_other_package_or_stale_version_is_rejected(self):
        payload, report = self.update_patch()
        for change in ({"package": "other"}, {"old_version": "1.0"}, {"version": "1.0"}):
            with self.subTest(change=change):
                with self.assertRaises(far.MaintenanceError):
                    workflow.apply_payload(self.package, payload, report | change, self.root / "body.md")
        self.assertEqual(self.run_git("diff"), b"")

    def test_mismatched_checksum_report_cannot_be_published(self):
        payload, report = self.update_patch()
        with self.assertRaisesRegex(far.MaintenanceError, "does not match"):
            workflow.apply_payload(self.package, payload, report | {"sha256": "0" * 64}, self.root / "body.md")

    def test_current_recipe_preparation_produces_no_patch(self):
        output = self.root / "outputs"
        with patch.object(workflow, "check_package"), \
                patch.object(workflow, "update_one", return_value={"status": "up-to-date"}):
            workflow.prepare(self.package, output)
        self.assertEqual(output.read_text(), "changed=false\n")


@unittest.skipUnless(shutil.which("makepkg") and shutil.which("shellcheck"), "requires Arch metadata tools")
class AurPublicationTests(unittest.TestCase):
    def test_new_support_files_survive_preparation_and_token_free_publication(self):
        with tempfile.TemporaryDirectory(prefix="far-handoff-tests-") as directory:
            root = Path(directory)
            prepare_root = root / "prepare"
            package = prepare_root / "packages" / "fixture"
            package.mkdir(parents=True)
            (package / "README.md").write_text("Fixture docs\n")
            (package / ".nvchecker.toml").write_text('[fixture]\nsource="aur"\naur="fixture"\n')
            far_aur.prepare_snapshot(package, "1" * 40, sources(), None)
            publish_root = root / "publish"
            shutil.copytree(prepare_root, publish_root)
            for checkout in (prepare_root, publish_root):
                subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
                subprocess.run(["git", "add", "."], cwd=checkout, check=True)
                subprocess.run(["git", "-c", "user.name=FAR tests", "-c", "user.email=far@example.invalid",
                                "commit", "-qm", "fixture"], cwd=checkout, check=True)
            new_sources = sources("1.1") | {"new-support.txt": b"new support\n"}
            output = root / "outputs"
            with patch.object(workflow, "ROOT", prepare_root), \
                    patch.object(far_aur, "fetch_snapshot", return_value=("2" * 40, new_sources)):
                workflow.prepare(package, output)
            values = dict(line.split("=", 1) for line in output.read_text().splitlines())
            report = json.loads(workflow.decode(values["report"]))
            with patch.object(workflow, "ROOT", publish_root), \
                    patch.object(far, "generate_srcinfo", side_effect=AssertionError("recipe evaluated")):
                workflow.apply_payload(publish_root / "packages" / "fixture",
                                       workflow.decode(values["patch"]), report, root / "body.md")
            self.assertEqual((publish_root / "packages/fixture/new-support.txt").read_bytes(), b"new support\n")
            far_aur.verify_manifest(publish_root / "packages" / "fixture")


if __name__ == "__main__":
    unittest.main()
