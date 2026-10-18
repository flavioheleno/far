"""Direct upstream updates for recipes with multiple sources and architectures."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shlex
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from far import MaintenanceError, assignment, check_package, generate_srcinfo, replace_assignment, set_assignment

MODES = {"github-assets", "freecad-weekly", "debian", "saleae", "fritzing"}
MAX_DOWNLOAD = 2 * 1024 ** 3


def validate_config(config: dict) -> None:
    if config.get("mode") not in MODES:
        raise MaintenanceError("Unknown direct upstream adapter")
    hosts = config.get("hosts", [])
    if not hosts or any(not isinstance(host, str) or not re.fullmatch(r"[a-z0-9.-]+", host) for host in hosts):
        raise MaintenanceError("Declare explicit upstream HTTPS hosts")
    fields = config.get("assignments", [])
    if ("pkgver" not in fields or len(fields) != len(set(fields))
            or any(not re.fullmatch(r"pkgver|_[A-Za-z0-9_]+", field) for field in fields)):
        raise MaintenanceError("Declare literal version and upstream assignments")
    if config["mode"] in {"github-assets", "freecad-weekly", "fritzing"}:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config.get("github", "")):
            raise MaintenanceError("Declare an explicit upstream GitHub repository")
    if config["mode"] in {"github-assets", "freecad-weekly"} and not isinstance(config.get("include_prereleases"), bool):
        raise MaintenanceError("Set include_prereleases explicitly to true or false")
    if config["mode"] == "fritzing" and not re.fullmatch(r"[A-Za-z0-9._/-]+", config.get("branch", "")):
        raise MaintenanceError("Declare the upstream source-version branch")
    identities = []
    for source in config.get("sources", []):
        if (source.get("variable") not in fields or not source["variable"].startswith("_url")
                or source.get("algorithm") not in {"sha256", "sha512"}
                or not re.fullmatch(r"sha(?:256|512)sums(?:_[a-z0-9_]+)?", source.get("array", ""))
                or type(source.get("index")) is not int or source["index"] < 0
                or not source["array"].startswith(source["algorithm"] + "sums")):
            raise MaintenanceError("Invalid upstream source/checksum mapping")
        identities.append((source["array"], source["index"]))
    if len(identities) != len(set(identities)):
        raise MaintenanceError("Duplicate upstream checksum mapping")


def validate_url(url: str, config: dict) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in config["hosts"]
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.fragment or any(char in url for char in "\n\r'\"`$\\<> ")):
        raise MaintenanceError(f"Unexpected upstream URL: {url}")
    return url


def open_upstream(url: str, config: dict, *, method: str = "GET"):
    validate_url(url, config)
    # Retry transient failures like request_json(); client errors fail immediately.
    for attempt in range(3):
        try:
            response = urlopen(Request(url, headers={"User-Agent": "far-recipe-updater"}, method=method), timeout=60)
            try:
                validate_url(response.geturl(), config)
            except BaseException:
                response.close()
                raise
            return response
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise MaintenanceError(f"Upstream request failed for {url}: HTTP {error.code}") from error
        except (URLError, TimeoutError) as error:
            if attempt == 2:
                raise MaintenanceError(f"Upstream request failed for {url}: {error}") from error
        time.sleep(2 ** attempt)
    raise MaintenanceError(f"Upstream request failed for {url}")


def fetch(url: str, config: dict, *, limit: int = 8 * 1024 ** 2) -> bytes:
    with open_upstream(url, config) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise MaintenanceError("Upstream metadata exceeds its size limit")
    return data


def checksum_values(recipe: str, array: str) -> list[str]:
    matches = re.findall(rf"^{re.escape(array)}=\((.*?)\)", recipe, re.M | re.S)
    if len(matches) != 1:
        raise MaintenanceError(f"Expected one literal {array} array")
    values = shlex.split(matches[0], comments=True)
    length = 64 if array.startswith("sha256") else 128
    if not values or any(value != "SKIP" and not re.fullmatch(rf"[a-f0-9]{{{length}}}", value) for value in values):
        raise MaintenanceError(f"Invalid {array} values")
    return values


def replace_checksum(recipe: str, source: dict, checksum: str) -> str:
    values = checksum_values(recipe, source["array"])
    if source["index"] >= len(values) or values[source["index"]] == "SKIP":
        raise MaintenanceError("Remote payloads must have a real checksum slot")
    values[source["index"]] = checksum
    rendered = "(" + "\n            ".join(f"'{value}'" for value in values) + ")"
    return re.sub(rf"^{re.escape(source['array'])}=\(.*?\)",
                  lambda _: source["array"] + "=" + rendered, recipe, count=1, flags=re.M | re.S)


def set_literal(recipe: str, name: str, value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._+:/?=&%~-]+", value):
        raise MaintenanceError(f"Unsafe literal assignment: {name}")
    return set_assignment(recipe, name, value)


def compare_versions(new: str, old: str) -> int:
    if any(not re.fullmatch(r"[0-9][A-Za-z0-9._+]*", value) for value in (new, old)):
        raise MaintenanceError("Unsupported upstream package version")
    result = subprocess.run(["vercmp", new, old], text=True, capture_output=True, check=True, timeout=10)
    return int(result.stdout.strip())


def publication_version_key(value: str) -> tuple[int, ...]:
    # These adapters emit numeric versions, optionally followed by a weekly date.
    # Keep publication portable: it runs on Ubuntu without Arch's vercmp.
    if not re.fullmatch(r"\d+(?:\.\d+)*(?:_\d+(?:\.\d+)*)?", value):
        raise MaintenanceError("Unsupported version in publication report")
    return tuple(int(part) for part in re.split(r"[._]", value))


def validate_candidate(candidate: dict, config: dict) -> None:
    fields = candidate.get("assignments", {})
    if set(fields) != set(config["assignments"]) or fields.get("pkgver") != candidate.get("version"):
        raise MaintenanceError("Candidate does not match configured upstream assignments")
    if type(candidate.get("prerelease")) is not bool:
        raise MaintenanceError("Declare the candidate release channel")
    validate_url(candidate["release_url"], config)
    if len(candidate.get("sources", [])) != len(config.get("sources", [])):
        raise MaintenanceError("Candidate does not cover every configured source")
    for source, expected in zip(candidate["sources"], config.get("sources", [])):
        if any(source.get(key) != expected[key] for key in ("variable", "array", "index", "algorithm")):
            raise MaintenanceError("Candidate changed its source/checksum mapping")
        if fields[source["variable"]] != source.get("url"):
            raise MaintenanceError("Candidate URL differs from its literal assignment")
        validate_url(source["url"], config)
        digest = source.get("digest")
        length = 64 if source["algorithm"] == "sha256" else 128
        if digest is not None and not re.fullmatch(rf"[a-f0-9]{{{length}}}", digest):
            raise MaintenanceError("Invalid published checksum")
        size = source.get("size")
        if size is not None and (type(size) is not int or not 0 < size <= MAX_DOWNLOAD):
            raise MaintenanceError("Invalid upstream download size")


def hash_source(source: dict, config: dict) -> str:
    digest = hashlib.new(source["algorithm"])
    size = 0
    with open_upstream(source["url"], config) as response:
        while block := response.read(1024 ** 2):
            size += len(block)
            if size > (source.get("size") or MAX_DOWNLOAD):
                raise MaintenanceError("Upstream payload exceeds its declared or maximum size")
            digest.update(block)
    if not size or (source.get("size") is not None and size != source["size"]):
        raise MaintenanceError("Upstream payload is empty or truncated")
    actual = digest.hexdigest()
    if source.get("digest") is not None and actual != source["digest"]:
        raise MaintenanceError("Downloaded checksum differs from upstream metadata")
    return actual


def render_recipe(recipe: str, candidate: dict) -> str:
    for name, value in candidate["assignments"].items():
        recipe = set_literal(recipe, name, value)
    recipe = replace_assignment(recipe, "pkgrel", "1")
    for source in candidate["sources"]:
        recipe = replace_checksum(recipe, source, source["checksum"])
    return recipe


def update_upstream(package: Path, config: dict, *, apply: bool, verify_current: bool) -> dict:
    from upstreams import discover
    path = package / "PKGBUILD"
    original = path.read_text()
    candidate = discover(package, config, original)
    validate_candidate(candidate, config)
    current = assignment(original, "pkgver")
    comparison = compare_versions(candidate["version"], current)
    if comparison < 0:
        raise MaintenanceError(f"Refusing downgrade: {current} -> {candidate['version']}")
    if comparison == 0 and any(assignment(original, key) != value for key, value in candidate["assignments"].items()):
        raise MaintenanceError("Upstream source changed at an unchanged version; review manually")
    for source in candidate["sources"]:
        old = checksum_values(original, source["array"])[source["index"]]
        if comparison == 0 and source.get("digest") not in (None, old):
            raise MaintenanceError("Upstream checksum changed at an unchanged version; review manually")
        source["checksum"] = (hash_source(source, config) if comparison or verify_current or source.get("digest") is None else old)
        if comparison == 0 and source["checksum"] != old:
            raise MaintenanceError("Current source no longer matches its committed checksum")
    if comparison == 0:
        return {"package": package.name, "status": "up-to-date", "version": current}
    report = candidate | {"package": package.name, "source": "upstream", "old_version": current,
                          "status": "updated" if apply else "available"}
    if apply:
        metadata = package / ".SRCINFO"
        previous = metadata.read_bytes()
        try:
            path.write_text(render_recipe(original, candidate))
            metadata.write_text(generate_srcinfo(package))
            check_package(package)
        except BaseException:
            path.write_text(original)
            metadata.write_bytes(previous)
            raise
    return report


def publication_body(package: Path, recipe: str, report: dict, config: dict) -> str:
    """Inspect only literal text; never load an adapter or evaluate shell here."""
    validate_candidate(report, config)
    if any(assignment(recipe, key) != value for key, value in report["assignments"].items()):
        raise MaintenanceError("Patched recipe does not match upstream assignments")
    rows = []
    for source in report["sources"]:
        value = checksum_values(recipe, source["array"])[source["index"]]
        if value != source.get("checksum") or value == "SKIP":
            raise MaintenanceError("Patched checksum does not match the update report")
        rows.append(f"- {source['url']}\n  {source['algorithm'].upper()}: `{value}`")
    rows.extend(f"- `{key}`: `{value}`" for key, value in report["assignments"].items()
                if key not in {"pkgver", *(item["variable"] for item in report["sources"])})
    verification = ("Payloads were hashed and metadata checked." if report["sources"] else
                    "The application commit was resolved from upstream's verified source-version bump. "
                    "A version bump may precede a public release. "
                    "The parts pin is retained: review its compatibility and the source patches locally.")
    return (f"Update `{package.name}` from **{report['old_version']}** to **{report['version']}**.\n\n"
            f"Upstream: {report['release_url']}\n\n" + "\n".join(rows) + "\n\n"
            f"Sources were resolved directly from upstream. {verification} "
            "No package was built or uploaded. Review packaging compatibility and test locally before installation.\n")
