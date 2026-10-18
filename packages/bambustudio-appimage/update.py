"""Resolve the official Ubuntu 24 x86_64 AppImage, including beta releases."""

import re

from far import MaintenanceError, normalize_tag, replace_assignment, version_key


def select_candidate(releases: list[dict], config: dict) -> dict:
    candidates = []
    for release in releases:
        if release.get("draft") or (release.get("prerelease") and not config["include_prereleases"]):
            continue
        tag = release["tag_name"]
        # Tags outside the configured four-part version scheme are not releases
        # of this package (for example, upstream's legacy or nightly tags).
        if not re.fullmatch(r"v\d{2}\.\d{2}\.\d{2}\.\d{2}", tag):
            continue
        candidates.append((normalize_tag(tag, config), release))
    if not candidates:
        raise MaintenanceError("No releases match the configured release channel and version scheme")
    version, release = max(candidates, key=lambda item: version_key(item[0]))
    tag = release["tag_name"]
    pattern = re.compile(rf"BambuStudio_(?:ubu24|ubuntu-?24\.04)-{re.escape(tag)}-\d{{14}}\.AppImage")
    assets = [asset for asset in release["assets"] if pattern.fullmatch(asset["name"])]
    if len(assets) != 1:
        raise MaintenanceError(f"{tag}: expected exactly one Ubuntu 24 AppImage; found {len(assets)}")
    asset = assets[0]
    url = f"https://github.com/{config['github']}/releases/download/{tag}/{asset['name']}"
    if asset["browser_download_url"] != url or asset.get("state") != "uploaded":
        raise MaintenanceError("Unexpected upstream asset URL or upload state")
    if type(asset["size"]) is not int or not 0 < asset["size"] <= 2 * 1024 ** 3:
        raise MaintenanceError("Invalid or excessive upstream asset size")
    digest = asset.get("digest")
    if digest is not None and not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise MaintenanceError("Unexpected upstream asset digest")
    return {"version": version, "tag": tag, "asset": asset["name"], "url": url,
            "size": asset["size"], "sha256": digest.removeprefix("sha256:") if digest else None,
            "release_url": f"https://github.com/{config['github']}/releases/tag/{tag}",
            "prerelease": release["prerelease"]}


def render_recipe(text: str, candidate: dict) -> str:
    for name, value in (("pkgver", candidate["version"]), ("pkgrel", "1"),
                        ("_upstream_tag", candidate["tag"]), ("_asset", candidate["asset"])):
        text = replace_assignment(text, name, value)
    return re.sub(r"^sha256sums=.*$", lambda _: f"sha256sums=('{candidate['sha256']}')", text, flags=re.M)
