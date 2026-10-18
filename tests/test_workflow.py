"""Exercise the text-only boundary between update preparation and publication."""

import base64
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import far
import far_upstream
import upstreams
import workflow
from test_upstream import DIGEST, bambu


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
        candidate = upstreams.github_assets(far.read_config(self.package), releases=[bambu()])
        for source in candidate["sources"]:
            source["checksum"] = DIGEST
        recipe.write_text(far_upstream.render_recipe(original, candidate))
        metadata = self.package / ".SRCINFO"
        metadata.write_text(metadata.read_text().replace("2.8.4.57", "2.8.5.1"))
        payload = self.run_git("diff", "--no-ext-diff", "--no-textconv")
        # Restore the fixture without reset/checkout commands or changing history.
        for file in (recipe, metadata):
            file.write_bytes(self.run_git("show", "HEAD:" + file.relative_to(self.root).as_posix()))
        report = candidate | {"package": self.package.name, "source": "upstream", "status": "updated",
                              "old_version": "2.8.4.57"}
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
        report = copy.deepcopy(report)
        report["sources"][0]["checksum"] = "0" * 64
        with self.assertRaisesRegex(far.MaintenanceError, "does not match"):
            workflow.apply_payload(self.package, payload, report, self.root / "body.md")

    def test_current_recipe_preparation_produces_no_patch(self):
        output = self.root / "outputs"
        with patch.object(workflow, "check_package"), \
                patch.object(workflow, "update_one", return_value={"status": "up-to-date"}):
            workflow.prepare(self.package, output)
        self.assertEqual(output.read_text(), "changed=false\n")


@unittest.skipUnless(shutil.which("makepkg") and shutil.which("shellcheck"), "requires Arch metadata tools")
class UpstreamPublicationTests(unittest.TestCase):
    def test_multi_source_format_prepares_and_publishes_without_arch_tools_in_publication(self):
        with tempfile.TemporaryDirectory(prefix="far-upstream-handoff-") as directory:
            root = Path(directory)
            prepare_root = root / "prepare"
            package = prepare_root / "packages" / "rtk-bin"
            shutil.copytree(ROOT / "packages/rtk-bin", package)
            config = far.read_config(package)
            payloads = []
            for entry in config["sources"]:
                name = entry.get("asset", "LICENSE")
                url = (f"https://github.com/rtk-ai/rtk/releases/download/v1.0.2/{name}" if "asset" in entry
                       else "https://github.com/rtk-ai/rtk/raw/v1.0.2/LICENSE")
                payloads.append(upstreams.source(config, entry["variable"], url, digest=DIGEST, size=10))
            selected = upstreams.candidate(config, "1.0.2", "https://github.com/rtk-ai/rtk/releases/tag/v1.0.2", payloads)
            publish_root = root / "publish"
            shutil.copytree(prepare_root, publish_root)
            for checkout in (prepare_root, publish_root):
                subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
                subprocess.run(["git", "add", "."], cwd=checkout, check=True)
                subprocess.run(["git", "-c", "user.name=FAR tests", "-c", "user.email=far@example.invalid",
                                "commit", "-qm", "fixture"], cwd=checkout, check=True)
            output = root / "outputs"
            with patch.object(workflow, "ROOT", prepare_root), \
                    patch.object(upstreams, "discover", return_value=selected), \
                    patch.object(far_upstream, "hash_source", return_value=DIGEST):
                workflow.prepare(package, output)
            values = dict(line.split("=", 1) for line in output.read_text().splitlines())
            report = json.loads(workflow.decode(values["report"]))
            with patch.object(workflow, "ROOT", publish_root), \
                    patch.object(far, "generate_srcinfo", side_effect=AssertionError("recipe evaluated")), \
                    patch.object(far_upstream, "compare_versions", side_effect=AssertionError("Arch tools unavailable")), \
                    patch.object(upstreams, "discover", side_effect=AssertionError("adapter evaluated")):
                workflow.apply_payload(publish_root / "packages/rtk-bin", workflow.decode(values["patch"]),
                                       report, root / "body.md")
            installed_recipe = (publish_root / "packages/rtk-bin/PKGBUILD").read_text()
            self.assertEqual(far.assignment(installed_recipe, "pkgver"), "1.0.2")
            for entry in config["sources"]:
                self.assertEqual(far_upstream.checksum_values(installed_recipe, entry["array"])[0], DIGEST)
            far.check_package(publish_root / "packages/rtk-bin")


if __name__ == "__main__":
    unittest.main()
