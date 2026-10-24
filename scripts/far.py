"""Shared recipe maintenance. No package build or install commands belong here."""

from __future__ import annotations

import argparse
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"[a-z0-9][a-z0-9@._+-]*")


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
    if config.get("source") != "upstream":
        raise MaintenanceError('Set source = "upstream" with a discovery mode')
    from far_upstream import validate_config
    validate_config(config)
    return config


def version_key(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise MaintenanceError(f"Unsupported package version: {version!r}")
    return tuple(int(part) for part in version.split("."))


def literal_pattern(name: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(name)}=(?:'([^'\n]*)'|\"([^\"\n]*)\"|([^\s'\"]+))$", re.M)


def assignment(text: str, name: str) -> str:
    matches = literal_pattern(name).findall(text)
    if len(matches) != 1:
        raise MaintenanceError(f"Expected one literal {name} assignment")
    value = next((value for value in matches[0] if value), "")
    if not value:
        raise MaintenanceError(f"Empty {name} assignment")
    return value


def replace_assignment(text: str, name: str, value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", value):
        raise MaintenanceError(f"Unsafe {name} value: {value!r}")
    return set_assignment(text, name, value)


def set_assignment(text: str, name: str, value: str) -> str:
    # Rewrite only the single literal line assignment() validated; leave computed ones alone.
    assignment(text, name)
    return literal_pattern(name).sub(lambda _: f"{name}='{value}'", text, count=1)


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
    read_config(package)
    for name in ("PKGBUILD", ".SRCINFO", ".nvchecker.toml", "README.md"):
        if not (package / name).is_file() or (package / name).is_symlink():
            raise MaintenanceError(f"Missing regular package file: {name}")
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
    if not set(architecture) & {"x86_64", "any"}:
        raise MaintenanceError("Recipe must support x86_64 or be architecture-independent")


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
        except (URLError, TimeoutError, HTTPException) as error:
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


def update_one(package: Path, releases: list[dict] | None = None, *,
               apply: bool = False, verify_current: bool = False) -> dict:
    from far_upstream import update_upstream
    return update_upstream(package, read_config(package), apply=apply,
                           verify_current=verify_current, releases=releases)


def check_main() -> int:
    parser = argparse.ArgumentParser(description="Check recipes and metadata; never build packages")
    parser.add_argument("packages", nargs="*", metavar="PKGBASE")
    args = parser.parse_args()
    failures = 0
    for package in package_paths(args.packages):
        try:
            check_package(package)
            print(f"{package.name}: recipe checks passed")
        except (MaintenanceError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
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
        except (MaintenanceError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
            result = {"package": package.name, "status": "error", "message": str(error)}
        results.append(result)
        print(json.dumps(result))
    if args.report:
        args.report.write_text(json.dumps(results, indent=2) + "\n")
    return any(result["status"] == "error" for result in results)


def cli(entry) -> None:
    try:
        raise SystemExit(entry())
    except (MaintenanceError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        print(f"far: {error}", file=sys.stderr)
        raise SystemExit(1) from error
