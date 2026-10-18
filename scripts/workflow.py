"""Pass bounded recipe patches between token-free checks and PR publication."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess

from far import (MaintenanceError, ROOT, assignment, check_package, cli,
                 package_paths, read_config, source_hash, update_one, version_key)

LIMIT = 64 * 1024


def git(*args: str, input: bytes | None = None) -> bytes:
    result = subprocess.run(["git", *args], cwd=ROOT, input=input, capture_output=True, check=False)
    if result.returncode:
        raise MaintenanceError(f"git {args[0]} failed: {result.stderr.decode().strip()}")
    return result.stdout


def encode(value: bytes) -> str:
    if len(value) > LIMIT:
        raise MaintenanceError("Update payload exceeds 64 KiB; review manually")
    return base64.b64encode(value).decode("ascii")


def decode(value: str) -> bytes:
    if len(value) > 4 * ((LIMIT + 2) // 3):
        raise MaintenanceError("Encoded update payload exceeds 64 KiB")
    result = base64.b64decode(value, validate=True)
    if not result or len(result) > LIMIT:
        raise MaintenanceError("Empty or oversized update payload")
    return result


def write_outputs(path: Path, outputs: dict[str, str]) -> None:
    if any("\n" in value or "\r" in value for value in outputs.values()):
        raise MaintenanceError("Workflow outputs must be single-line values")
    path.write_text("".join(f"{key}={value}\n" for key, value in outputs.items()))


def allowed_paths(package: Path) -> set[str]:
    return {f"packages/{package.name}/PKGBUILD", f"packages/{package.name}/.SRCINFO"}


def prepare(package: Path, output: Path) -> None:
    if git("status", "--porcelain").strip():
        raise MaintenanceError("Prepare updates from a clean checkout")
    check_package(package)
    report = update_one(package, apply=True)
    if report["status"] == "up-to-date":
        write_outputs(output, {"changed": "false"})
        print(f"{package.name}: up to date")
        return
    # Include new/deleted AUR support files in the patch, including new files.
    git("add", "--all", "--", f"packages/{package.name}")
    changed = set(git("diff", "--name-only", "--no-renames", "HEAD").decode().splitlines())
    if report.get("source") == "aur":
        allowed = {f"packages/{package.name}/{name}" for name in
                   [*report["files"], *report["removed_files"], ".aur.json"]}
        valid = changed <= allowed and f"packages/{package.name}/.aur.json" in changed
    else:
        valid = changed == allowed_paths(package)
    if not valid or git("ls-files", "--others", "--exclude-standard").strip():
        raise MaintenanceError("Updater changed files outside the expected recipe and .SRCINFO")
    patch = git("diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "--", *sorted(changed))
    write_outputs(output, {"changed": "true", "patch": encode(patch),
                           "report": encode(json.dumps(report).encode())})
    print(f"{package.name}: prepared {report['old_version']} -> {report['version']}")


def apply_payload(package: Path, patch: bytes, report: dict, body_path: Path) -> dict[str, str]:
    """Validate data and apply a patch, without evaluating the updated recipe."""
    config = read_config(package)
    aur = config["source"] == "aur"
    upstream = config["source"] == "upstream"
    if aur:
        from far_aur import publication_body, publication_paths
        allowed = publication_paths(package, report)
    elif upstream:
        from far_upstream import validate_candidate
        if report.get("package") != package.name or report.get("status") != "updated" or report.get("source") != "upstream":
            raise MaintenanceError("Invalid upstream update report")
        validate_candidate(report, config)
        allowed = allowed_paths(package)
    elif (report.get("package") != package.name or report.get("status") != "updated"
            or not re.fullmatch(r"[a-f0-9]{64}", report.get("sha256", ""))
            or not re.fullmatch(r"[A-Za-z0-9._+-]+", report.get("asset", ""))
            or type(report.get("prerelease")) is not bool):
        raise MaintenanceError("Invalid update report")
    else:
        allowed = allowed_paths(package)
    if not aur:
        current = assignment((package / "PKGBUILD").read_text(), "pkgver")
        if upstream:
            from far_upstream import compare_versions
            advances = compare_versions(report["version"], current) > 0
        else:
            advances = version_key(report["version"]) > version_key(current)
        if current != report.get("old_version") or not advances:
            raise MaintenanceError("Update report is stale or does not advance the version")
    if git("status", "--porcelain").strip():
        raise MaintenanceError("Apply updates to a clean checkout")
    stats = git("apply", "--numstat", "-", input=patch).decode().splitlines()
    fields = [line.split("\t", 2) for line in stats]
    for row in fields:
        if len(row) != 3:
            raise MaintenanceError("Invalid recipe patch statistics")
        text = row[0].isdigit() and row[1].isdigit()
        public_key = (aur and row[:2] == ["-", "-"] and re.fullmatch(
            rf"packages/{re.escape(package.name)}/keys/pgp/[A-Za-z0-9._+-]+\.(?:asc|gpg)", row[2]))
        if not text and not public_key:
            raise MaintenanceError("Only recipe text and imported public signing keys are accepted")
    paths = [row[2] for row in fields]
    valid = (set(paths) <= allowed and f"packages/{package.name}/.aur.json" in paths) if aur else (
        set(paths) == allowed and len(paths) == 2)
    if not valid:
        raise MaintenanceError("Patch must modify only the selected PKGBUILD and .SRCINFO")
    git("apply", "--check", "-", input=patch)
    git("apply", "-", input=patch)
    if any((ROOT / path).is_symlink() or ((ROOT / path).exists() and not (ROOT / path).is_file()) for path in paths):
        raise MaintenanceError("Patched recipe files must remain regular files")
    if not aur and any(not (ROOT / path).is_file() for path in paths):
        raise MaintenanceError("Direct update patches must retain both recipe files")
    if aur:
        body_path.write_text(publication_body(package, report))
        return {"title": f"chore({package.name}): update AUR recipe to {report['version']}",
                "body-path": str(body_path)}
    recipe = (package / "PKGBUILD").read_text()
    if upstream:
        from far_upstream import publication_body
        body_path.write_text(publication_body(package, recipe, report, config))
        return {"title": f"chore({package.name}): update to {report['version']}",
                "body-path": str(body_path)}
    tag = assignment(recipe, "_upstream_tag")
    expected_url = f"https://github.com/{read_config(package)['github']}/releases/tag/{tag}"
    if (assignment(recipe, "pkgver") != report["version"]
            or assignment(recipe, "_asset") != report["asset"]
            or source_hash(recipe) != report["sha256"]
            or report.get("release_url") != expected_url):
        raise MaintenanceError("Patched recipe does not match the update report")
    channel = "beta / prerelease" if report["prerelease"] else "stable"
    body_path.write_text(
        f"Update `{package.name}` from **{current}** to **{report['version']}**.\n\n"
        f"- Upstream: {expected_url}\n- Release channel: {channel}\n"
        f"- Asset: `{report['asset']}`\n- SHA-256: `{report['sha256']}`\n\n"
        "The upstream download was hashed and recipe metadata was regenerated and checked. "
        "No package was built or uploaded. Review the diff, merge, and build/install locally.\n")
    return {"title": f"chore({package.name}): update to {report['version']}",
            "body-path": str(body_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("matrix", "prepare", "apply"))
    parser.add_argument("--output", type=Path, default=Path(os.environ.get("GITHUB_OUTPUT", "/tmp/far-outputs")))
    args = parser.parse_args()
    package_name = os.environ.get("PACKAGE", "")
    packages = package_paths([package_name] if package_name else None)
    if args.command == "matrix":
        write_outputs(args.output, {"packages": json.dumps([package.name for package in packages])})
        return 0
    if len(packages) != 1 or not package_name:
        raise MaintenanceError("Set PACKAGE to exactly one known package base")
    package = packages[0]
    if args.command == "prepare":
        prepare(package, args.output)
    else:
        body_path = args.output.parent / "far-update-body.md"
        outputs = apply_payload(package, decode(os.environ["UPDATE_PATCH"]),
                                json.loads(decode(os.environ["UPDATE_REPORT"])), body_path)
        write_outputs(args.output, outputs)
    return 0


if __name__ == "__main__":
    cli(main)
