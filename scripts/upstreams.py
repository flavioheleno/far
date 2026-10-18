"""Resolve first-party releases. This module never reads or contacts AUR."""

import json
import re
from datetime import datetime
from html import unescape
from urllib.parse import urljoin

from far import MaintenanceError, assignment, github_releases, version_key
from far_upstream import compare_versions, fetch, open_upstream, validate_url


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


def debian_entries(data: bytes) -> list[dict]:
    entries = []
    for paragraph in re.split(r"\n\s*\n", data.decode().replace("\r\n", "\n").strip()):
        fields = {}
        for line in paragraph.splitlines():
            if line.startswith((" ", "\t")):
                continue  # Description continuations are not discovery fields.
            key, separator, value = line.partition(":")
            if not separator or key in fields:
                raise MaintenanceError("Malformed or duplicate Debian package metadata")
            fields[key] = value.strip()
        entries.append(fields)
    return entries


def debian_version(value: str) -> tuple[str, dict]:
    spotify = re.fullmatch(r"(\d+(?:\.\d+){3})\.(g[a-f0-9]+)", value)
    if spotify:
        return spotify[1], {"_commit": spotify[2]}
    if not re.fullmatch(r"\d+(?:\.\d+)*(?:-\d+)?", value):
        raise MaintenanceError(f"Unrecognized upstream Debian version: {value}")
    return value.replace("-", "."), {}


def debian(config: dict, *, indices=None) -> dict:
    sources = []
    versions = set()
    extra_fields = None
    for entry in config["sources"]:
        url = entry["index_url"]
        records = debian_entries(indices[url] if indices is not None else fetch(url, config))
        eligible = [record for record in records if record.get("Package") == config["package"]
                    and record.get("Architecture") == entry["architecture"]]
        if not eligible:
            raise MaintenanceError(f"No {config['package']} for {entry['architecture']} in upstream index")
        normalized = [(debian_version(record["Version"]), record) for record in eligible]
        # Use Arch version comparison on complete normalized versions, retaining vendor build IDs.
        best = normalized[0]
        for item in normalized[1:]:
            if compare_versions(item[0][0], best[0][0]) > 0:
                best = item
        (version, fields), record = best
        if sum(item[0][0] == version for item in normalized) != 1:
            raise MaintenanceError("Ambiguous highest-version Debian payload")
        versions.add(version)
        if extra_fields is not None and extra_fields != fields:
            raise MaintenanceError("Architectures disagree on upstream build identifiers")
        extra_fields = fields
        filename = record["Filename"]
        if (not filename.startswith("pool/") or any(part in {".", "..", ""} for part in filename.split("/"))
                or not filename.endswith(".deb")):
            raise MaintenanceError("Unexpected upstream Debian payload path")
        payload_url = urljoin(config["base_url"], filename)
        digest = record[entry["algorithm"].upper()]
        try:
            size = int(record["Size"])
        except ValueError as error:
            raise MaintenanceError("Invalid Debian payload size") from error
        sources.append(source(config, entry["variable"], payload_url, digest=digest, size=size))
    if len(versions) != 1:
        raise MaintenanceError("Upstream architectures have different versions; wait for a complete release")
    return candidate(config, versions.pop(), config["release_url"], sources, fields=extra_fields,
                     prerelease=config.get("prerelease", False))


def sublime(config: dict) -> dict:
    page = fetch(config["release_url"], config).decode()
    text = unescape(re.sub(r"<[^>]+>", " ", page))
    builds = re.findall(r"Version:\s*Build\s+(\d+)", text)
    if len(set(builds)) != 1:
        raise MaintenanceError("Expected one current Sublime Text development build")
    build = builds[0]
    sources = [source(config, item["variable"],
                      f"https://download.sublimetext.com/sublime_text_build_{build}_{item['architecture']}.tar.xz")
               for item in config["sources"]]
    return candidate(config, f"4.{build}", config["release_url"], sources, prerelease=True)


def saleae(config: dict) -> dict:
    with open_upstream(config["endpoint"], config, method="HEAD") as response:
        url = response.geturl()
        length = response.headers.get("Content-Length")
    match = re.fullmatch(r"https://downloads2\.saleae\.com/logic2/Logic-(\d+(?:\.\d+){2})-linux-x64\.AppImage", url)
    if not match:
        raise MaintenanceError("Saleae download redirect did not select a versioned Linux x64 AppImage")
    payload = source(config, "_url", url, size=int(length) if length else None)
    return candidate(config, match[1], config["release_url"], [payload])


def discover(package, config: dict, recipe: str) -> dict:
    if config["mode"] == "github-assets":
        return github_assets(config)
    if config["mode"] == "freecad-weekly":
        return freecad_weekly(config, recipe)
    if config["mode"] == "debian":
        return debian(config)
    if config["mode"] == "sublime":
        return sublime(config)
    if config["mode"] == "saleae":
        return saleae(config)
    raise MaintenanceError(f"Upstream discovery not implemented: {config['mode']}")
