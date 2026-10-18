"""Shared recipe maintenance. No package build or install commands belong here."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"[a-z0-9][a-z0-9@._+-]*")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class MaintenanceError(Exception):
    """An actionable maintenance failure."""


def package_paths(names: list[str] | None = None, root: Path = ROOT) -> list[Path]:
    available = {
        path.name: path for path in sorted((root / "packages").iterdir())
        if path.is_dir() and not path.is_symlink() and (path / "PKGBUILD").is_file()
    }
    selected = names or list(available)
    if not selected:
        raise MaintenanceError("No packages found")
    for name in selected:
        if not NAME.fullmatch(name) or name not in available:
            raise MaintenanceError(f"Unknown package base: {name}")
    return [available[name] for name in dict.fromkeys(selected)]


def read_config(package: Path) -> dict:
    data = tomllib.loads((package / ".nvchecker.toml").read_text())
    if set(data) != {package.name}:
        raise MaintenanceError(".nvchecker.toml must contain exactly its pkgbase table")
    config = data[package.name]
    repository = config.get("github")
    if (config.get("source") != "github" or not isinstance(repository, str)
            or not REPOSITORY.fullmatch(repository)):
        raise MaintenanceError("Updater currently supports GitHub owner/repo release sources")
    if config.get("use_max_release") is not True:
        raise MaintenanceError("Set use_max_release = true to select releases by version")
    if not isinstance(config.get("include_prereleases"), bool):
        raise MaintenanceError("Set include_prereleases explicitly to true or false")
    return config


def normalize_tag(tag: str, config: dict) -> str:
    prefix = config.get("prefix", "")
    version = tag.removeprefix(prefix)
    pattern = config.get("from_pattern")
    if pattern:
        if not re.fullmatch(pattern, version):
            raise MaintenanceError(f"Unrecognized upstream tag: {tag}")
        version = re.sub(pattern, config["to_pattern"], version)
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise MaintenanceError(f"Expected a numeric dotted version, got {version!r}")
    return version


def version_key(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise MaintenanceError(f"Unsupported package version: {version!r}")
    return tuple(int(part) for part in version.split("."))


def assignment(text: str, name: str) -> str:
    matches = re.findall(rf"^{re.escape(name)}=(?:'([^'\n]*)'|\"([^\"\n]*)\"|([^\s'\"]+))$", text, re.M)
    if len(matches) != 1:
        raise MaintenanceError(f"Expected one literal {name} assignment")
    value = next((value for value in matches[0] if value), "")
    if not value:
        raise MaintenanceError(f"Empty {name} assignment")
    return value


def replace_assignment(text: str, name: str, value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", value):
        raise MaintenanceError(f"Unsafe {name} value: {value!r}")
    assignment(text, name)
    return re.sub(rf"^{re.escape(name)}=.*$", lambda _: f"{name}='{value}'", text, flags=re.M)


def source_hash(text: str) -> str:
    matches = re.findall(r"^sha256sums=\('([a-f0-9]{64})'\)$", text, re.M)
    if len(matches) != 1:
        raise MaintenanceError("Expected one literal SHA-256 checksum")
    return matches[0]


def generate_srcinfo(package: Path) -> str:
    # Recipes are executable shell. Do not pass automation credentials to makepkg.
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR"}}
    result = subprocess.run(
        ["makepkg", "--printsrcinfo"], cwd=package, env=env,
        text=True, capture_output=True, check=False, timeout=60,
    )
    if result.returncode:
        raise MaintenanceError(f"makepkg metadata failed: {result.stderr.strip()}")
    if not result.stdout.startswith(f"pkgbase = {package.name}\n"):
        raise MaintenanceError("Directory name must match generated pkgbase")
    return result.stdout


def check_package(package: Path) -> None:
    for name in ("PKGBUILD", ".SRCINFO", ".nvchecker.toml", "update.py", "README.md"):
        if not (package / name).is_file() or (package / name).is_symlink():
            raise MaintenanceError(f"Missing regular package file: {name}")
    read_config(package)
    for command in (
        ["bash", "-n", "PKGBUILD"],
        ["shellcheck", "--shell=bash", "--exclude=SC2034,SC2154", "PKGBUILD"],
    ):
        result = subprocess.run(command, cwd=package, check=False, timeout=60)
        if result.returncode:
            raise MaintenanceError(f"{command[0]} rejected PKGBUILD")
    generated = generate_srcinfo(package)
    if generated != (package / ".SRCINFO").read_text():
        raise MaintenanceError("Stale .SRCINFO; regenerate with makepkg --printsrcinfo")
    architecture = re.findall(r"^\s+arch = (.+)$", generated, re.M)
    if not architecture or not set(architecture) <= {"x86_64", "any"}:
        raise MaintenanceError("FAR currently targets x86_64 and architecture-independent packages")


def request_json(url: str) -> list:
    headers = {"User-Agent": "far-recipe-updater", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=60) as response:
                data = json.load(response)
            if not isinstance(data, list):
                raise MaintenanceError("Expected a GitHub release list")
            return data
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise MaintenanceError(f"GitHub request failed with HTTP {error.code}") from error
        except (URLError, TimeoutError) as error:
            if attempt == 2:
                raise MaintenanceError(f"GitHub request failed: {error}") from error
        time.sleep(2 ** attempt)
    raise MaintenanceError("GitHub request failed")


def github_releases(repository: str) -> list[dict]:
    releases = []
    for page in range(1, 11):
        batch = request_json(f"https://api.github.com/repos/{repository}/releases?per_page=100&page={page}")
        releases.extend(batch)
        if len(batch) < 100:
            return releases
    raise MaintenanceError("Release pagination exceeds 1,000 entries; review the discovery policy")


def download_hash(candidate: dict) -> str:
    digest = hashlib.sha256()
    total = 0
    # Public asset downloads deliberately carry no GitHub token across redirects.
    request = Request(candidate["url"], headers={"User-Agent": "far-recipe-updater"})
    with urlopen(request, timeout=60) as response:
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > candidate["size"]:
                raise MaintenanceError("Downloaded asset exceeds its declared size")
            digest.update(block)
    if total != candidate["size"]:
        raise MaintenanceError("Downloaded asset size differs from release metadata")
    actual = digest.hexdigest()
    if candidate["sha256"] is not None and actual != candidate["sha256"]:
        raise MaintenanceError("Downloaded SHA-256 differs from GitHub's asset digest")
    return actual


def update_one(package: Path, releases: list[dict] | None = None, *,
               apply: bool = False, verify_current: bool = False) -> dict:
    config = read_config(package)
    adapter = runpy.run_path(str(package / "update.py"))
    candidate = adapter["select_candidate"](
        github_releases(config["github"]) if releases is None else releases, config)
    path = package / "PKGBUILD"
    original = path.read_text()
    current = assignment(original, "pkgver")
    comparison = (version_key(candidate["version"]) > version_key(current)) - (
        version_key(candidate["version"]) < version_key(current))
    if comparison < 0:
        raise MaintenanceError(f"Refusing downgrade: {current} -> {candidate['version']}")
    old_hash = source_hash(original)
    if comparison == 0:
        if (assignment(original, "_upstream_tag") != candidate["tag"]
                or assignment(original, "_asset") != candidate["asset"]
                or candidate["sha256"] not in (None, old_hash)):
            raise MaintenanceError("Upstream asset changed at an unchanged version; review manually")
        if verify_current or candidate["sha256"] is None:
            if download_hash(candidate) != old_hash:
                raise MaintenanceError("Current source no longer matches the committed checksum")
        return {"package": package.name, "status": "up-to-date", "version": current}
    candidate["sha256"] = download_hash(candidate)
    updated = adapter["render_recipe"](original, candidate)
    result = {"package": package.name, "status": "updated" if apply else "available",
              "old_version": current, "version": candidate["version"],
              "release_url": candidate["release_url"], "asset": candidate["asset"],
              "sha256": candidate["sha256"], "prerelease": candidate["prerelease"]}
    if apply:
        srcinfo_path = package / ".SRCINFO"
        old_srcinfo = srcinfo_path.read_bytes()
        try:
            path.write_text(updated)
            srcinfo_path.write_text(generate_srcinfo(package))
            check_package(package)
        except BaseException:
            path.write_text(original)
            srcinfo_path.write_bytes(old_srcinfo)
            raise
    return result


def check_main() -> int:
    parser = argparse.ArgumentParser(description="Check recipes and metadata; never build packages")
    parser.add_argument("packages", nargs="*", metavar="PKGBASE")
    args = parser.parse_args()
    failures = 0
    for package in package_paths(args.packages):
        try:
            check_package(package)
            print(f"{package.name}: recipe checks passed")
        except (MaintenanceError, OSError, ValueError, subprocess.TimeoutExpired) as error:
            failures += 1
            print(f"{package.name}: {error}", file=sys.stderr)
    return bool(failures)


def update_main() -> int:
    parser = argparse.ArgumentParser(description="Discover or apply recipe updates; never build packages")
    parser.add_argument("packages", nargs="*", metavar="PKGBASE")
    parser.add_argument("--apply", action="store_true", help="write recipe and generated .SRCINFO")
    parser.add_argument("--list", action="store_true", help="list package bases as JSON, then exit")
    parser.add_argument("--verify-current", action="store_true", help="also download/hash unchanged sources")
    parser.add_argument("--releases-json", type=Path, help="use saved GitHub release metadata instead of the API")
    parser.add_argument("--report", type=Path, help="write a JSON summary (including failures)")
    args = parser.parse_args()
    packages = package_paths(args.packages)
    if args.list:
        print(json.dumps([package.name for package in packages]))
        return 0
    if args.releases_json and len(packages) != 1:
        parser.error("--releases-json requires exactly one package")
    releases = json.loads(args.releases_json.read_text()) if args.releases_json else None
    results = []
    for package in packages:
        try:
            result = update_one(package, releases, apply=args.apply, verify_current=args.verify_current)
        except (MaintenanceError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            result = {"package": package.name, "status": "error", "message": str(error)}
        results.append(result)
        print(json.dumps(result))
    if args.report:
        args.report.write_text(json.dumps(results, indent=2) + "\n")
    return any(result["status"] == "error" for result in results)


def cli(entry) -> None:
    try:
        raise SystemExit(entry())
    except (MaintenanceError, OSError, ValueError) as error:
        print(f"far: {error}", file=sys.stderr)
        raise SystemExit(1) from error
