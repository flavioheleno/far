"""Reviewable AUR snapshot updates with explicit, persistent local overlays."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile

from far import MaintenanceError, NAME, check_package, generate_srcinfo

RESERVED = {"README.md", "AGENTS.md", ".nvchecker.toml", ".aur.json", "far.patch", "update.py"}
REVISION = re.compile(r"[a-f0-9]{40}")
MAX_FILE = 2 * 1024 * 1024


def source_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (bool(path.parts) and not path.is_absolute() and name == path.as_posix()
            and all(re.fullmatch(r"[A-Za-z0-9_+@.-]+", part) for part in path.parts)
            and not any(part in {".", ".."} or part.startswith(".") for part in path.parts
                        if name != ".SRCINFO")
            and path.parts[0] not in RESERVED
            and not re.search(r"(?:\.AppImage|\.pkg\.tar\..*|\.src\.tar\..*)$", name))


def command(args: list[str], cwd: Path) -> bytes:
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR"}}
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, check=False, timeout=120)
    if result.returncode:
        raise MaintenanceError(f"{args[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def snapshot(checkout: Path) -> tuple[str, dict[str, bytes]]:
    revision = command(["git", "rev-parse", "HEAD"], checkout).decode().strip()
    if not REVISION.fullmatch(revision):
        raise MaintenanceError("Unexpected AUR Git revision")
    files = {}
    for entry in command(["git", "ls-tree", "-rz", "HEAD"], checkout).split(b"\0"):
        if not entry:
            continue
        header, raw_name = entry.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        name = raw_name.decode()
        if name in {".gitignore", ".SRCINFO"}:
            continue  # FAR regenerates metadata and owns its ignore rules.
        if not source_path(name):
            raise MaintenanceError(f"Unsupported or reserved AUR source path: {name}")
        if mode not in {"100644", "100755"} or kind != "blob":
            raise MaintenanceError(f"AUR source must be a regular file: {name}")
        size = int(command(["git", "cat-file", "-s", oid], checkout))
        if size > MAX_FILE:
            raise MaintenanceError(f"AUR support file exceeds 2 MiB: {name}")
        files[name] = command(["git", "cat-file", "blob", oid], checkout)
    if "PKGBUILD" not in files:
        raise MaintenanceError("AUR snapshot has no PKGBUILD")
    return revision, files


def fetch_snapshot(name: str, directory: Path) -> tuple[str, dict[str, bytes]]:
    if not NAME.fullmatch(name):
        raise MaintenanceError("Invalid AUR package name")
    command(["git", "clone", "--quiet", "--depth", "1",
             f"https://aur.archlinux.org/{name}.git", str(directory)], directory.parent)
    return snapshot(directory)


def write_sources(package: Path, files: dict[str, bytes]) -> None:
    for name, content in files.items():
        if not source_path(name) or len(content) > MAX_FILE:
            raise MaintenanceError(f"Invalid source file: {name}")
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def metadata_version(text: str) -> str:
    values = {}
    for name in ("epoch", "pkgver", "pkgrel"):
        matches = re.findall(rf"^\s+{name} = (\S+)$", text, re.M)
        if len(matches) > 1:
            raise MaintenanceError(f"Repeated {name} in .SRCINFO")
        values[name] = matches[0] if matches else None
    if not values["pkgver"] or not values["pkgrel"]:
        raise MaintenanceError("Incomplete version in .SRCINFO")
    version = f"{values['pkgver']}-{values['pkgrel']}"
    if values["epoch"] not in (None, "0"):
        version = f"{values['epoch']}:{version}"
    if not re.fullmatch(r"[A-Za-z0-9._+:]+-[0-9]+(?:\.[0-9]+)?", version):
        raise MaintenanceError("Invalid Arch package version")
    return version


def manifest(package: Path, revision: str, names: list[str]) -> dict:
    return {"revision": revision, "files": {
        name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in sorted(names)}}


def read_manifest(package: Path) -> dict:
    data = json.loads((package / ".aur.json").read_text())
    if (set(data) != {"revision", "files"} or not REVISION.fullmatch(data.get("revision", ""))
            or not isinstance(data["files"], dict)
            or not {"PKGBUILD", ".SRCINFO"} <= data["files"].keys()):
        raise MaintenanceError("Invalid .aur.json snapshot manifest")
    for name, digest in data["files"].items():
        if not source_path(name) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise MaintenanceError("Invalid source path or checksum in .aur.json")
    return data


def verify_manifest(package: Path) -> None:
    for name, digest in read_manifest(package)["files"].items():
        path = package / name
        if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(package.resolve())
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise MaintenanceError(f"Snapshot file differs from .aur.json: {name}; update its overlay and manifest")


def prepare_snapshot(package: Path, revision: str, files: dict[str, bytes], overlay: Path | None) -> None:
    write_sources(package, files)
    if overlay is not None:
        shutil.copy2(overlay, package / "far.patch")
        rows = command(["git", "apply", "--numstat", str(package / "far.patch")], package).decode().splitlines()
        if not rows or any(row.split("\t", 2)[-1] not in files for row in rows):
            raise MaintenanceError("Local overlays may change only imported AUR source files")
        # Outside a Git worktree, git apply treats paths relative to this directory.
        command(["git", "apply", "--check", str(package / "far.patch")], package)
        command(["git", "apply", str(package / "far.patch")], package)
    (package / ".SRCINFO").write_text(generate_srcinfo(package))
    data = manifest(package, revision, [*files, ".SRCINFO"])
    (package / ".aur.json").write_text(json.dumps(data, indent=2) + "\n")


def update_aur(package: Path, *, apply: bool = False) -> dict:
    verify_manifest(package)
    previous = read_manifest(package)
    current = metadata_version((package / ".SRCINFO").read_text())
    with tempfile.TemporaryDirectory(prefix="far-aur-") as directory:
        root = Path(directory)
        revision, files = fetch_snapshot(package.name, root / "upstream")
        if revision == previous["revision"]:
            return {"package": package.name, "status": "up-to-date", "version": current, "source": "aur"}
        target = root / "snapshot" / package.name
        target.mkdir(parents=True)
        for name in (".nvchecker.toml", "README.md"):
            shutil.copy2(package / name, target / name)
        overlay = package / "far.patch"
        prepare_snapshot(target, revision, files, overlay if overlay.is_file() else None)
        check_package(target)
        version = metadata_version((target / ".SRCINFO").read_text())
        if int(command(["vercmp", version, current], target)) < 0:
            raise MaintenanceError(f"Refusing AUR downgrade: {current} -> {version}")
        result = {"package": package.name, "source": "aur", "status": "updated" if apply else "available",
                  "old_version": current, "version": version, "old_revision": previous["revision"],
                  "revision": revision, "files": sorted(read_manifest(target)["files"]),
                  "removed_files": sorted(set(previous["files"]) - set(read_manifest(target)["files"])),
                  "release_url": f"https://aur.archlinux.org/cgit/aur.git/commit/?h={package.name}&id={revision}"}
        if apply:
            managed = set(previous["files"]) | set(result["files"]) | {".aur.json"}
            originals = {name: (package / name).read_bytes() if (package / name).is_file() else None for name in managed}
            try:
                for name in managed:
                    source = target / name
                    if source.is_file():
                        (package / name).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, package / name)
                    else:
                        (package / name).unlink(missing_ok=True)
                check_package(package)
            except BaseException:
                for name, content in originals.items():
                    if content is None:
                        (package / name).unlink(missing_ok=True)
                    else:
                        (package / name).write_bytes(content)
                raise
        return result


def publication_paths(package: Path, report: dict) -> set[str]:
    previous = read_manifest(package)
    if (report.get("package") != package.name or report.get("status") != "updated"
            or report.get("old_revision") != previous["revision"]
            or not REVISION.fullmatch(report.get("revision", ""))
            or report["revision"] == previous["revision"]
            or not isinstance(report.get("files"), list)
            or any(not isinstance(name, str) or not source_path(name) for name in report["files"])
            or not {"PKGBUILD", ".SRCINFO"} <= set(report["files"])):
        raise MaintenanceError("Invalid or stale AUR update report")
    if metadata_version((package / ".SRCINFO").read_text()) != report.get("old_version"):
        raise MaintenanceError("Stale AUR package version")
    names = set(previous["files"]) | set(report["files"]) | {".aur.json"}
    return {f"packages/{package.name}/{name}" for name in names}


def publication_body(package: Path, report: dict) -> str:
    data = read_manifest(package)
    verify_manifest(package)
    expected_url = f"https://aur.archlinux.org/cgit/aur.git/commit/?h={package.name}&id={data['revision']}"
    if (data["revision"] != report["revision"] or sorted(data["files"]) != sorted(report["files"])
            or metadata_version((package / ".SRCINFO").read_text()) != report.get("version")
            or report.get("release_url") != expected_url):
        raise MaintenanceError("Patched AUR snapshot does not match its report")
    return (f"Update `{package.name}` from **{report['old_version']}** to **{report['version']}**.\n\n"
            f"AUR revision: {expected_url}\n\n"
            "The AUR recipe and supporting files were imported, the checked-in FAR overlay "
            "was reapplied, and metadata and file hashes were checked. Vendor source checksums "
            "are retained from AUR and verified by makepkg locally. No package was built or "
            "uploaded. Review all recipe and supporting-file changes before merging.\n")
