"""Resolve first-party releases. This module never reads or contacts AUR."""

import json
import re
from datetime import datetime

from far import MaintenanceError, assignment, github_releases, version_key
from far_upstream import fetch, validate_url


def source(config: dict, variable: str, url: str, *, digest=None, size=None) -> dict:
    matches = [item for item in config["sources"] if item["variable"] == variable]
    if len(matches) != 1:
        raise MaintenanceError(f"Missing or ambiguous source mapping: {variable}")
    return matches[0] | {"url": validate_url(url, config), "digest": digest, "size": size}


def candidate(config: dict, version: str, release_url: str, sources: list[dict], *, fields=None, prerelease=False) -> dict:
    # Source order is part of the publication contract.
    by_variable = {item["variable"]: item for item in sources}
    ordered = [by_variable[item["variable"]] for item in config["sources"]]
    return {"version": version, "release_url": release_url, "prerelease": prerelease,
            "assignments": {"pkgver": version, **(fields or {}),
                            **{item["variable"]: item["url"] for item in ordered}}, "sources": ordered}


def latest_release(config: dict, *, weekly=False) -> dict:
    eligible = []
    for release in github_releases(config["github"]):
        if release.get("draft") or (release.get("prerelease") and not config["include_prereleases"]):
            continue
        tag = release["tag_name"]
        pattern = r"weekly-(\d{4}\.\d{2}\.\d{2})" if weekly else r"v?(\d+(?:\.\d+)+)"
        match = re.fullmatch(pattern, tag)
        if match:
            if weekly:
                datetime.strptime(match[1], "%Y.%m.%d")
            eligible.append((version_key(match[1]), release))
    if not eligible:
        raise MaintenanceError("No upstream releases match the configured channel/version scheme")
    return max(eligible, key=lambda item: item[0])[1]


def asset_source(config: dict, release: dict, variable: str, name: str) -> dict:
    assets = [item for item in release["assets"] if item["name"] == name]
    if len(assets) != 1:
        raise MaintenanceError(f"Expected exactly one {name} asset; found {len(assets)}")
    asset = assets[0]
    url = f"https://github.com/{config['github']}/releases/download/{release['tag_name']}/{name}"
    if asset.get("state") != "uploaded" or asset["browser_download_url"] != url:
        raise MaintenanceError("Unexpected GitHub asset state or URL")
    digest = asset.get("digest")
    if digest is not None and not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise MaintenanceError("Unexpected GitHub asset digest")
    size = asset.get("size")
    if type(size) is not int or not 0 < size <= 2 * 1024 ** 3:
        raise MaintenanceError("Invalid GitHub asset size")
    return source(config, variable, url, digest=digest.removeprefix("sha256:") if digest else None, size=size)


def github_assets(config: dict) -> dict:
    release = latest_release(config)
    tag = release["tag_name"]
    version = tag.removeprefix("v")
    sources = [asset_source(config, release, item["variable"], item["asset"]) for item in config["sources"] if "asset" in item]
    sources.append(source(config, "_url_license", f"https://github.com/{config['github']}/raw/{tag}/LICENSE"))
    return candidate(config, version, f"https://github.com/{config['github']}/releases/tag/{tag}", sources,
                     prerelease=release["prerelease"])


def freecad_weekly(config: dict, recipe: str) -> dict:
    release = latest_release(config, weekly=True)
    tag = release["tag_name"]
    date = tag.removeprefix("weekly-")
    if tag == assignment(recipe, "_upstream_tag"):
        version = assignment(recipe, "pkgver")
    else:
        data = json.loads(fetch(f"https://raw.githubusercontent.com/{config['github']}/{tag}/version.json", config))
        parts = [data[f"version_{part}"] for part in ("major", "minor", "patch")]
        if any(type(part) is not int or part < 0 for part in parts):
            raise MaintenanceError("Invalid FreeCAD version.json")
        version = ".".join(map(str, parts)) + "_" + date
    payload = asset_source(config, release, "_url", f"FreeCAD_{tag}-Linux-x86_64.AppImage")
    return candidate(config, version, f"https://github.com/{config['github']}/releases/tag/{tag}", [payload],
                     fields={"_upstream_tag": tag}, prerelease=True)


def discover(package, config: dict, recipe: str) -> dict:
    if config["mode"] == "github-assets":
        return github_assets(config)
    if config["mode"] == "freecad-weekly":
        return freecad_weekly(config, recipe)
    raise MaintenanceError(f"Upstream discovery not implemented: {config['mode']}")
