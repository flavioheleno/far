"""Exercise local build orchestration with fake Arch commands."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


COMMAND = """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys

command, args = Path(sys.argv[0]).name, sys.argv[1:]
with open(os.environ["FAR_TEST_LOG"], "a") as log:
    log.write(json.dumps({"command": command, "args": args, "cwd": str(Path.cwd())}) + "\\n")
if command == "sudo":
    sys.exit(subprocess.call(args))
if command == "pacman":
    if args == ["-Q"]:
        if os.environ.get("FAR_TEST_FAILURE") == "query":
            sys.exit(1)
        print(os.environ.get("FAR_TEST_INSTALLED", ""), end="")
    sys.exit(0)
if command == "vercmp":
    if os.environ.get("FAR_TEST_FAILURE") == "compare":
        sys.exit(1)
    left, right = [version.removeprefix("0:") for version in args]
    print(0 if left == right else 1)
    sys.exit(0)
name = Path.cwd().name
destination = Path(os.environ["PKGDEST"])
files = [destination / f"{name}-2.0-x86_64.pkg.tar.zst"]
if name == "alpha":
    files.append(destination / "alpha-docs-2.0-any.pkg.tar.zst")
failure = os.environ.get("FAR_TEST_FAILURE") if name == "alpha" else None
if args == ["-s"]:
    if failure == "build":
        sys.exit(1)
    for file in [*files, destination / f"{name}-debug-2.0-x86_64.pkg.tar.zst"]:
        file.write_text("fresh")
        Path(str(file) + ".sig").write_text("signature")
    print("build output is not an archive path")
elif args == ["--packagelist"]:
    if failure == "list":
        sys.exit(1)
    if failure != "empty":
        print(*files, destination / f"{name}-debug-2.0-x86_64.pkg.tar.zst", sep="\\n")
else:
    sys.exit("unexpected makepkg arguments")
"""


class BuildPackagesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="far build test ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "scripts").mkdir()
        self.script = self.root / "scripts" / "build-packages"
        shutil.copy2(Path(__file__).resolve().parents[1] / "scripts" / "build-packages", self.script)
        for name in ("alpha", "beta", "not-a-package"):
            package = self.root / "packages" / name
            package.mkdir(parents=True)
            if name != "not-a-package":
                (package / "PKGBUILD").touch()
                metadata = (f"pkgbase = {name}\n\tpkgver = 2.0\n\tpkgrel = 1\n"
                            f"\tarch = x86_64\n\npkgname = {name}\n")
                if name == "alpha":
                    metadata += "\npkgname = alpha-docs\n"
                (package / ".SRCINFO").write_text(metadata)
                (package / f"{name}-1.0-x86_64.pkg.tar.zst").write_text("stale")
        (self.root / "packages" / "linked").symlink_to(self.root / "packages" / "alpha",
                                                      target_is_directory=True)
        binary = self.root / "bin"
        binary.mkdir()
        for name in ("makepkg", "sudo", "pacman", "vercmp"):
            command = binary / name
            command.write_text(COMMAND)
            command.chmod(0o755)
        self.tmpdir = self.root / "temporary files"
        self.tmpdir.mkdir()
        self.old_output = self.root / "old output"
        self.old_output.mkdir()
        (self.old_output / "alpha-debug-2.0-x86_64.pkg.tar.zst").write_text("stale")
        self.log = self.root / "commands.jsonl"
        self.env = os.environ | {"PATH": f"{binary}:{os.environ['PATH']}",
                                 "TMPDIR": str(self.tmpdir), "PKGDEST": str(self.old_output),
                                 "FAR_TEST_LOG": str(self.log), "FAR_TEST_FAILURE": "",
                                 "FAR_TEST_INSTALLED": ""}

    def run_script(self, *args, **env):
        self.log.write_text("")
        result = subprocess.run([str(self.script), *args], cwd=self.root.parent,
                                env=self.env | env, text=True, capture_output=True, timeout=10)
        return result, [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_builds_every_package_then_installs_only_fresh_archives_once(self):
        result, commands = self.run_script(
            FAR_TEST_INSTALLED="alpha 2.0-1\nalpha-docs 2.0-1\nbeta 2.0-1\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        builds = [entry for entry in commands if entry["command"] == "makepkg" and entry["args"] == ["-s"]]
        self.assertEqual([Path(entry["cwd"]).name for entry in builds], ["alpha", "beta"])
        installs = [entry for entry in commands if entry["command"] == "pacman"]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0], commands[-1])
        self.assertEqual(len([entry for entry in commands if entry["command"] == "sudo"]), 1)
        self.assertEqual(installs[0]["args"][:2], ["-U", "--"])
        archives = [Path(file) for file in installs[0]["args"][2:]]
        self.assertEqual([file.name for file in archives],
                         ["alpha-2.0-x86_64.pkg.tar.zst", "alpha-docs-2.0-any.pkg.tar.zst",
                          "beta-2.0-x86_64.pkg.tar.zst"])
        self.assertEqual({file.parent.parent for file in archives}, {self.tmpdir})
        self.assertTrue(all(file.read_text() == "fresh" for file in archives))

    def test_failure_still_attempts_other_packages_but_never_installs(self):
        for failure in ("build", "list", "empty"):
            with self.subTest(failure=failure):
                result, commands = self.run_script(FAR_TEST_FAILURE=failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("alpha", result.stderr)
                self.assertEqual([Path(entry["cwd"]).name for entry in commands
                                  if entry["command"] == "makepkg" and entry["args"] == ["-s"]],
                                 ["alpha", "beta"])
                self.assertFalse(any(entry["command"] in ("sudo", "pacman") for entry in commands))

    def test_no_recipes_does_not_install(self):
        for name in ("alpha", "beta"):
            (self.root / "packages" / name / "PKGBUILD").unlink()
        result, commands = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No packages found", result.stderr)
        self.assertEqual(commands, [])

    def test_needed_builds_only_missing_or_different_versions(self):
        metadata = self.root / "packages" / "alpha" / ".SRCINFO"
        metadata.write_text(metadata.read_text().replace(
            "\tpkgver = 2.0\n", "\tpkgver = 2.0.99_2026.11.14\n\tepoch = 1\n"))
        installed = "alpha 1:2.0.99_2026.11.14-1\nalpha-docs 1:2.0.99_2026.11.14-1\n"
        for version in (None, "1.0-1", "2.0-2", "1:2.0-1", "3.0-1"):
            with self.subTest(installed_beta=version):
                snapshot = installed + (f"beta {version}\n" if version else "")
                result, commands = self.run_script("--needed", FAR_TEST_INSTALLED=snapshot)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([Path(entry["cwd"]).name for entry in commands
                                  if entry["command"] == "makepkg" and entry["args"] == ["-s"]],
                                 ["beta"])
                installs = [entry for entry in commands
                            if entry["command"] == "pacman" and entry["args"][:1] == ["-U"]]
                self.assertEqual(len(installs), 1)
                self.assertEqual([Path(file).name for file in installs[0]["args"][2:]],
                                 ["beta-2.0-x86_64.pkg.tar.zst"])

    def test_needed_requires_all_split_packages_to_match(self):
        metadata = self.root / "packages" / "beta" / ".SRCINFO"
        metadata.write_text(metadata.read_text().replace("\tpkgrel = 1\n", "\tpkgrel = 1\n\tepoch = 0\n"))
        for docs_version, expected_builds in ((None, ["alpha"]), ("1.0-1", ["alpha"]), ("2.0-1", [])):
            with self.subTest(installed_docs=docs_version):
                snapshot = "alpha 2.0-1\nbeta 2.0-1\n"
                if docs_version:
                    snapshot += f"alpha-docs {docs_version}\n"
                before = set(self.tmpdir.iterdir())
                result, commands = self.run_script("--needed", FAR_TEST_INSTALLED=snapshot)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([Path(entry["cwd"]).name for entry in commands
                                  if entry["command"] == "makepkg" and entry["args"] == ["-s"]],
                                 expected_builds)
                if not expected_builds:
                    self.assertIn("All packages are already installed", result.stdout)
                    self.assertFalse(any(entry["command"] == "sudo" for entry in commands))
                    self.assertFalse(any(entry["command"] == "pacman" and entry["args"][:1] == ["-U"]
                                         for entry in commands))
                    self.assertEqual(set(self.tmpdir.iterdir()), before)

    def test_needed_metadata_and_database_failures_never_install(self):
        metadata = self.root / "packages" / "alpha" / ".SRCINFO"
        original = metadata.read_text()
        for failure in ("query", "compare", "missing-metadata", "invalid-metadata", "empty-package-name"):
            with self.subTest(failure=failure):
                metadata.write_text(original)
                if failure == "missing-metadata":
                    metadata.unlink()
                elif failure == "invalid-metadata":
                    metadata.write_text("pkgbase = another-package\n")
                elif failure == "empty-package-name":
                    metadata.write_text(original.replace("\npkgname = alpha\n", "\npkgname = \n"))
                result, commands = self.run_script(
                    "--needed", FAR_TEST_FAILURE=failure,
                    FAR_TEST_INSTALLED="alpha 2.0-1\nalpha-docs 2.0-1\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(result.stderr)
                if failure == "empty-package-name":
                    self.assertIn("Invalid .SRCINFO", result.stderr)
                self.assertFalse(any(entry["command"] == "sudo" or
                                     (entry["command"] == "pacman" and entry["args"][:1] == ["-U"])
                                     for entry in commands))

    def test_invalid_arguments_do_not_build_or_install(self):
        for args in (("--unknown",), ("--needed", "extra")):
            with self.subTest(args=args):
                result, commands = self.run_script(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Usage:", result.stderr)
                self.assertEqual(commands, [])
                self.assertEqual(list(self.tmpdir.iterdir()), [])
