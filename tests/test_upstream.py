"""Direct upstream integrity checks; no network or package builds."""

import hashlib
import io
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import far
import far_upstream as upstream
import upstreams

CONFIG = {"source": "upstream", "mode": "debian", "hosts": ["vendor.example"],
          "assignments": ["pkgver", "_url"],
          "sources": [{"variable": "_url", "array": "sha256sums", "index": 0, "algorithm": "sha256"}]}
PAYLOAD = b"fixture payload"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
RECIPE = "pkgver=1.0\npkgrel=4\n_url='https://vendor.example/1.0.deb'\nsha256sums=('" + "0" * 64 + "'\n '" + "1" * 64 + "')\n"


def candidate():
    return {"version": "1.1", "release_url": "https://vendor.example/releases", "prerelease": False,
            "assignments": {"pkgver": "1.1", "_url": "https://vendor.example/1.1.deb"},
            "sources": [CONFIG["sources"][0] | {"url": "https://vendor.example/1.1.deb",
                         "size": len(PAYLOAD), "digest": DIGEST, "checksum": DIGEST}]}


class IntegrityTests(unittest.TestCase):
    def test_source_mapping_and_urls_cannot_escape_configuration(self):
        upstream.validate_config(CONFIG)
        upstream.validate_candidate(candidate(), CONFIG)
        for change in ({"url": "http://vendor.example/1.1.deb"}, {"array": "sha512sums"},
                       {"size": True}, {"digest": "bad"}, {"url": "https://other.example/payload"}):
            data = candidate()
            data["sources"][0].update(change)
            with self.assertRaises(far.MaintenanceError):
                upstream.validate_candidate(data, CONFIG)

    def test_hashes_streams_and_rejects_corrupt_or_truncated_payloads(self):
        for payload in (PAYLOAD, PAYLOAD[:-1], PAYLOAD + b"x", b"x" * len(PAYLOAD)):
            with patch.object(upstream, "open_upstream", return_value=io.BytesIO(payload)):
                if payload == PAYLOAD:
                    self.assertEqual(upstream.hash_source(candidate()["sources"][0], CONFIG), DIGEST)
                else:
                    with self.assertRaises(far.MaintenanceError):
                        upstream.hash_source(candidate()["sources"][0], CONFIG)

    def test_updates_one_checksum_and_preserves_supporting_file_checksums(self):
        rendered = upstream.render_recipe(RECIPE, candidate())
        self.assertEqual(upstream.checksum_values(rendered, "sha256sums"), [DIGEST, "1" * 64])
        self.assertEqual(far.assignment(rendered, "pkgver"), "1.1")
        self.assertEqual(far.assignment(rendered, "pkgrel"), "1")

    def test_transient_upstream_failures_retry_but_client_errors_do_not(self):
        from urllib.error import HTTPError
        url = "https://vendor.example/Packages"
        response = io.BytesIO(b"index")
        response.geturl = lambda: url
        def error(code):
            return HTTPError(url, code, "fixture", {}, None)
        with patch.object(upstream, "urlopen", side_effect=[error(503), TimeoutError(), response]) as request, \
                patch.object(upstream.time, "sleep") as sleep:
            self.assertIs(upstream.open_upstream(url, CONFIG), response)
        self.assertEqual((request.call_count, sleep.call_count), (3, 2))
        for side_effect, calls in (([error(404)], 1), ([error(503)] * 3, 3)):
            with patch.object(upstream, "urlopen", side_effect=side_effect) as request, \
                    patch.object(upstream.time, "sleep"):
                with self.assertRaises(far.MaintenanceError):
                    upstream.open_upstream(url, CONFIG)
            self.assertEqual(request.call_count, calls)

    def test_checksum_replacement_edits_only_the_selected_value(self):
        old, keep = "a" * 64, "b" * 64
        recipe = (f"sha256sums_x86_64=(\"{keep}\"  # launcher\n"
                  f"    {old}\n    'SKIP')\nsha256sums=('{keep}')\n")
        source = {"array": "sha256sums_x86_64", "index": 1}
        rendered = upstream.replace_checksum(recipe, source, DIGEST)
        self.assertEqual(rendered, recipe.replace(f"    {old}\n", f"    '{DIGEST}'\n"))
        for index, value in ((2, DIGEST), (1, "f" * 128), (1, "not-a-checksum")):
            with self.assertRaises(far.MaintenanceError):
                upstream.replace_checksum(recipe, source | {"index": index}, value)

    def test_literal_rewrite_leaves_computed_assignments_untouched(self):
        recipe = RECIPE + "_url=$(printf %s \"$base\")\n"
        rendered = upstream.set_literal(recipe, "_url", "https://vendor.example/1.1.deb")
        self.assertIn("_url='https://vendor.example/1.1.deb'\n", rendered)
        self.assertIn("_url=$(printf %s \"$base\")\n", rendered)
        rendered = far.replace_assignment(recipe + "pkgrel=$((1 + 1))\n", "pkgrel", "1")
        self.assertIn("pkgrel='1'\n", rendered)
        self.assertIn("pkgrel=$((1 + 1))\n", rendered)

    def test_publication_checks_literals_without_executing_recipe(self):
        rendered = upstream.render_recipe(RECIPE, candidate())
        report = candidate() | {"old_version": "1.0"}
        with patch.object(far, "generate_srcinfo", side_effect=AssertionError("executed recipe")):
            body = upstream.publication_body(Path("fixture"), rendered, report, CONFIG)
        self.assertIn(DIGEST, body)
        report["sources"][0]["checksum"] = "f" * 64
        with self.assertRaises(far.MaintenanceError):
            upstream.publication_body(Path("fixture"), rendered, report, CONFIG)

    def test_arch_version_comparison_preserves_dated_builds(self):
        self.assertGreater(upstream.compare_versions("1.2.0_2026.10.21", "1.2.0_2026.10.14"), 0)
        self.assertLess(upstream.compare_versions("1.0", "2.0"), 0)
        with patch.object(upstream.subprocess, "run", side_effect=AssertionError("Arch tools unavailable")):
            self.assertGreater(upstream.publication_version_key("1.2.0_2026.10.21"),
                               upstream.publication_version_key("1.2.0_2026.10.14"))


class GithubDiscoveryTests(unittest.TestCase):
    def config(self, name):
        return far.read_config(Path(__file__).resolve().parents[1] / "packages" / name)

    def release(self, config, tag):
        return {"tag_name": tag, "draft": False, "prerelease": False, "assets": [
            {"name": entry["asset"], "size": len(PAYLOAD), "digest": "sha256:" + DIGEST,
             "state": "uploaded", "browser_download_url":
             f"https://github.com/{config['github']}/releases/download/{tag}/{entry['asset']}"}
            for entry in config["sources"] if "asset" in entry]}

    def test_release_channel_must_be_explicit(self):
        for name in ("rtk-bin", "freecad-weekly-appimage"):
            config = self.config(name)
            for value in (None, "false"):
                broken = {key: item for key, item in config.items() if key != "include_prereleases"}
                if value is not None:
                    broken["include_prereleases"] = value
                with self.subTest(name=name, value=value), \
                        self.assertRaisesRegex(far.MaintenanceError, "include_prereleases"):
                    upstream.validate_config(broken)

    def test_rtk_and_tailwind_include_both_architectures_and_release_license(self):
        for name in ("rtk-bin", "tailwindcss-bin"):
            config = self.config(name)
            data = self.release(config, "v99.1.0")
            with patch.object(upstreams, "github_releases", return_value=[data]):
                selected = upstreams.github_assets(config)
            upstream.validate_candidate(selected, config)
            self.assertEqual(selected["version"], "99.1.0")
            self.assertEqual(len(selected["sources"]), 3)
            self.assertIn("/raw/v99.1.0/LICENSE", selected["assignments"]["_url_license"])
            data["assets"].pop()
            with patch.object(upstreams, "github_releases", return_value=[data]):
                with self.assertRaisesRegex(far.MaintenanceError, "found 0"):
                    upstreams.github_assets(config)

    def test_newest_missing_asset_does_not_fall_back_to_an_older_release(self):
        config = self.config("rtk-bin")
        newest = self.release(config, "v99.1.0")
        newest["assets"] = []
        with patch.object(upstreams, "github_releases", return_value=[newest, self.release(config, "v1.0.0")]):
            with self.assertRaises(far.MaintenanceError):
                upstreams.github_assets(config)

    def test_freecad_uses_tagged_version_json_and_complete_weekly_date(self):
        config = self.config("freecad-weekly-appimage")
        tag = "weekly-2026.10.21"
        name = f"FreeCAD_{tag}-Linux-x86_64.AppImage"
        data = {"tag_name": tag, "prerelease": True, "draft": False, "assets": [
            {"name": name, "size": 100, "digest": "sha256:" + DIGEST, "state": "uploaded",
             "browser_download_url": f"https://github.com/FreeCAD/FreeCAD/releases/download/{tag}/{name}"}]}
        recipe = "pkgver=1.2.0_2026.10.14\n_upstream_tag='weekly-2026.10.14'\n"
        with patch.object(upstreams, "github_releases", return_value=[data]), \
                patch.object(upstreams, "fetch", return_value=b'{"version_major":1,"version_minor":2,"version_patch":0}') as fetch:
            selected = upstreams.freecad_weekly(config, recipe)
        upstream.validate_candidate(selected, config)
        self.assertEqual(selected["version"], "1.2.0_2026.10.21")
        self.assertIn(f"/{tag}/version.json", fetch.call_args.args[0])


def appimage_release(package, tag, name, *, beta=False):
    repository = {"bambustudio-appimage": "bambulab/BambuStudio", "extrudo-appimage": "zoltanf/extrudo"}[package]
    return {"tag_name": tag, "draft": False, "prerelease": beta,
            "assets": [{"name": name, "state": "uploaded", "size": len(PAYLOAD), "digest": f"sha256:{DIGEST}",
                        "browser_download_url": f"https://github.com/{repository}/releases/download/{tag}/{name}"}]}


def bambu(tag="v02.08.05.01", *, beta=True, variant="ubu24", stamp="20261017123456"):
    return appimage_release("bambustudio-appimage", tag, f"BambuStudio_{variant}-{tag}-{stamp}.AppImage", beta=beta)


def extrudo(version="0.8.0", *, beta=False):
    return appimage_release("extrudo-appimage", f"v{version}", f"extrudo-{version}-linux-x86_64.AppImage", beta=beta)


class AppImageDiscoveryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "packages"
        self.bambu = far.read_config(root / "bambustudio-appimage")
        self.extrudo = far.read_config(root / "extrudo-appimage")

    def select(self, config, releases):
        selected = upstreams.github_assets(config, releases=releases)
        upstream.validate_candidate(selected, config)
        return selected

    def test_bambu_selects_highest_zero_padded_version_and_tracks_betas(self):
        draft = bambu("v99.00.00.01")
        draft["draft"] = True
        releases = [draft, bambu("v02.08.03.99"), bambu(), bambu("v02.08.04.99"), bambu("v02.08.02.61", beta=False)]
        self.assertEqual(self.select(self.bambu, releases)["version"], "2.8.5.1")
        stable = self.select(self.bambu | {"include_prereleases": False}, releases)
        self.assertEqual((stable["version"], stable["prerelease"]), ("2.8.2.61", False))

    def test_bambu_ignores_other_tag_schemes(self):
        self.assertEqual(self.select(self.bambu, [bambu("v2.9.0.1"), bambu("nightly-02.09.00.01"), bambu()])["version"],
                         "2.8.5.1")

    def test_bambu_accepts_known_ubuntu24_asset_names_only(self):
        for variant in ("ubu24", "ubuntu24.04", "ubuntu-24.04"):
            with self.subTest(variant=variant):
                self.assertIn(variant, self.select(self.bambu, [bambu(variant=variant)])["assignments"]["_url"])
        for name in ("BambuStudio_ubu22-v02.08.05.01-20261017123456.AppImage",
                     "BambuStudio_ubu24-v02.08.05.01-20261017123456-aarch64.AppImage",
                     "BambuStudio_ubu24-v02.08.04.57-20261017123456.AppImage"):
            data = bambu()
            data["assets"][0]["name"] = name
            with self.subTest(name=name), self.assertRaisesRegex(far.MaintenanceError, "found 0"):
                self.select(self.bambu, [data, bambu("v02.08.04.57")])

    def test_bambu_duplicate_assets_and_bad_metadata_require_review(self):
        data = bambu()
        data["assets"].extend(bambu(stamp="20261017123457")["assets"])
        with self.assertRaisesRegex(far.MaintenanceError, "found 2"):
            self.select(self.bambu, [data])
        for field, value in (("browser_download_url", "https://example.org/asset.AppImage"), ("state", "starter"),
                             ("size", 0), ("size", True), ("digest", "sha256:bad")):
            data = bambu()
            data["assets"][0][field] = value
            with self.subTest(field=field), self.assertRaises(far.MaintenanceError):
                self.select(self.bambu, [data])

    def test_extrudo_tracks_stable_linux_x86_64_only(self):
        selected = self.select(self.extrudo, [extrudo("1.0.0", beta=True), extrudo("0.7.0"), extrudo()])
        self.assertEqual(selected["version"], "0.8.0")
        self.assertTrue(selected["assignments"]["_url"].endswith("/v0.8.0/extrudo-0.8.0-linux-x86_64.AppImage"))
        for assets in ([], extrudo()["assets"] * 2,
                       [extrudo()["assets"][0] | {"name": "extrudo-0.8.0-linux-aarch64.AppImage"}]):
            with self.subTest(assets=assets), self.assertRaises(far.MaintenanceError):
                self.select(self.extrudo, [extrudo() | {"assets": assets}])

    def test_committed_recipes_match_their_current_release(self):
        root = Path(__file__).resolve().parents[1] / "packages"
        for config, data in ((self.bambu, bambu("v02.08.04.57", stamp="20260922164607")), (self.extrudo, extrudo("0.7.0"))):
            package = root / ("bambustudio-appimage" if config is self.bambu else "extrudo-appimage")
            recipe = (package / "PKGBUILD").read_text()
            data["assets"][0]["digest"] = "sha256:" + upstream.checksum_values(recipe, "sha256sums")[0]
            with self.subTest(package=package.name), \
                    patch.object(upstream, "hash_source", side_effect=AssertionError("should not download")):
                result = far.update_one(package, [data])
            self.assertEqual(result["status"], "up-to-date")

    def test_saved_releases_apply_only_to_github_modes(self):
        root = Path(__file__).resolve().parents[1] / "packages"
        with self.assertRaisesRegex(far.MaintenanceError, "GitHub release modes"):
            far.update_one(root / "enpass-bin", [bambu()])


class VendorDiscoveryTests(unittest.TestCase):
    def config(self, name):
        return far.read_config(Path(__file__).resolve().parents[1] / "packages" / name)

    def index(self, package="enpass", architecture="amd64", version="6.12.7.2300", filename=None):
        return (f"Package: {package}\nArchitecture: {architecture}\nVersion: {version}\n"
                f"Filename: {filename or 'pool/main/e/enpass/enpass_' + version + '_' + architecture + '.deb'}\n"
                f"Size: {len(PAYLOAD)}\nSHA256: {DIGEST}\nDescription: fixture\n continuation\n\n").encode()

    def test_debian_selection_filters_package_and_architecture_and_uses_full_version(self):
        config = self.config("enpass-bin")
        data = (self.index(version="6.12.7.2200") + self.index() + self.index(package="unrelated", version="99.0")
                + self.index(architecture="arm64", version="99.0"))
        with patch.object(upstreams, "fetch", return_value=data):
            selected = upstreams.debian(config)
        upstream.validate_candidate(selected, config)
        self.assertEqual(selected["version"], "6.12.7.2300")
        self.assertEqual(selected["sources"][0]["digest"], DIGEST)

    def test_debian_duplicate_versions_and_traversal_are_rejected(self):
        config = self.config("enpass-bin")
        for data in (self.index() * 2, self.index(filename="pool/../../payload.deb"),
                     self.index().replace(b"SHA256:", b"Size: 42\nSHA256:")):
            with patch.object(upstreams, "fetch", return_value=data):
                with self.assertRaises(far.MaintenanceError):
                    upstreams.debian(config)

    def test_tableplus_retains_build_number_and_waits_for_both_architectures(self):
        config = self.config("tableplus")
        data = {entry["index_url"]: self.index(package="tableplus", architecture=entry["architecture"],
                                             version="2.0.0-318") for entry in config["sources"]}
        selected = upstreams.debian(config, indices=data)
        upstream.validate_candidate(selected, config)
        self.assertEqual(selected["version"], "2.0.0.318")
        entry = config["sources"][1]
        data[entry["index_url"]] = self.index(package="tableplus", architecture="arm64", version="2.0.0-317")
        with self.assertRaisesRegex(far.MaintenanceError, "different versions"):
            upstreams.debian(config, indices=data)

    def test_saleae_uses_versioned_redirect_and_rejects_insider_or_foreign_downloads(self):
        config = self.config("saleae-logic2")
        class Response(io.BytesIO):
            headers = {"Content-Length": "15"}
            url = "https://downloads2.saleae.com/logic2/Logic-2.4.49-linux-x64.AppImage"
            def geturl(self):
                return self.url
        with patch.object(upstreams, "open_upstream", return_value=Response()) as request:
            selected = upstreams.saleae(config)
        upstream.validate_candidate(selected, config)
        self.assertEqual(selected["version"], "2.4.49")
        self.assertEqual(request.call_args.kwargs["method"], "HEAD")
        for url in (Response.url.replace("2.4.49", "2.4.49-insider"), "https://other.example/payload"):
            response = Response()
            response.url = url
            with patch.object(upstreams, "open_upstream", return_value=response):
                with self.assertRaises(far.MaintenanceError):
                    upstreams.saleae(config)


class SignedSpotifyTests(unittest.TestCase):
    def setUp(self):
        self.package = Path(__file__).resolve().parents[1] / "packages" / "spotify"
        self.config = far.read_config(self.package)
        self.index = ("Package: spotify-client\nArchitecture: amd64\nVersion: 1.3.5.300.gabcdef123456\n"
                      "Filename: pool/non-free/s/spotify-client/spotify-client_1.3.5.300.gabcdef123456_amd64.deb\n"
                      f"Size: {len(PAYLOAD)}\nSHA512: {hashlib.sha512(PAYLOAD).hexdigest()}\n\n").encode()
        self.path = "non-free/binary-amd64/Packages"
        self.release = f"SHA256:\n {hashlib.sha256(self.index).hexdigest()} {len(self.index)} {self.path}\nSHA512:\n".encode()

    def test_signed_index_chain_selects_complete_spotify_build(self):
        data = {self.config["release_url"]: self.release,
                self.config["release_url"] + ".gpg": b"fixture signature",
                self.config["sources"][0]["index_url"]: self.index}
        with patch.object(upstreams, "fetch", side_effect=lambda url, config: data[url]), \
                patch.object(upstreams, "verify_release_signature") as verify:
            selected = upstreams.signed_debian(self.package, self.config)
        verify.assert_called_once_with(self.package, self.config, self.release, b"fixture signature")
        upstream.validate_candidate(selected, self.config)
        self.assertEqual(selected["version"], "1.3.5.300")
        self.assertEqual(selected["assignments"]["_commit"], "gabcdef123456")
        self.assertEqual(selected["sources"][0]["digest"], hashlib.sha512(PAYLOAD).hexdigest())

    def test_signed_index_hash_size_and_section_are_enforced(self):
        upstreams.verify_index(self.release, self.index, self.path)
        for release, index in ((self.release, self.index + b"x"), (self.release * 2, self.index),
                               (self.release.replace(b"SHA256:", b"MD5Sum:"), self.index)):
            with self.assertRaises(far.MaintenanceError):
                upstreams.verify_index(release, index, self.path)

    def test_bad_signature_or_unreviewed_fingerprint_is_rejected(self):
        import subprocess
        for code, fingerprint in ((1, self.config["signing_key"]), (0, "F" * 40)):
            imported = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
            verified = subprocess.CompletedProcess([], code, stdout=f"[GNUPG:] VALIDSIG {fingerprint} 0\n", stderr="")
            with patch.object(upstreams.subprocess, "run", side_effect=[imported, verified]):
                with self.assertRaisesRegex(far.MaintenanceError, "signature failed"):
                    upstreams.verify_release_signature(self.package, self.config, self.release, b"signature")

    def test_co_signature_from_a_retired_key_is_ignored_but_other_failures_fail(self):
        key = self.config["signing_key"]
        good = (f"[GNUPG:] NEWSIG\n[GNUPG:] GOODSIG {key[-16:]} Vendor\n"
                f"[GNUPG:] VALIDSIG {key} 2026-01-01 0 0 4 0 1 10 00 {key}\n")
        retired = ("[GNUPG:] NEWSIG\n[GNUPG:] ERRSIG 6F7565879798C2FC 1 8 00 0 9 " + "B" * 40 +
                   "\n[GNUPG:] NO_PUBKEY 6F7565879798C2FC\n")
        exit_failure = "[GNUPG:] FAILURE gpg-exit 33554433\n"
        cases = (
            (good + retired + exit_failure, True),
            # A non-missing-key error (rc 4: unknown algorithm) is not tolerated.
            (good + retired.replace(" 0 9 ", " 0 4 ") + exit_failure, False),
            (good + "[GNUPG:] NEWSIG\n[GNUPG:] BADSIG 6F7565879798C2FC Old\n" + exit_failure, False),
            # A valid detached signature followed by extra data must not pass.
            ("[GNUPG:] NODATA 3\n" + good + exit_failure, False),
            (f"[GNUPG:] NEWSIG\n[GNUPG:] EXPKEYSIG {key[-16:]} Vendor\n" + good.split("\n")[2] + "\n", False),
            (retired + exit_failure, False),
        )
        for stdout, accepted in cases:
            imported = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
            verified = subprocess.CompletedProcess([], 2, stdout=stdout, stderr="")
            with self.subTest(stdout=stdout), \
                    patch.object(upstreams.subprocess, "run", side_effect=[imported, verified]):
                if accepted:
                    upstreams.verify_release_signature(self.package, self.config, self.release, b"signature")
                else:
                    with self.assertRaises(far.MaintenanceError):
                        upstreams.verify_release_signature(self.package, self.config, self.release, b"signature")

    def test_local_recipe_preserves_wget_epoch_and_signature_policy(self):
        recipe = (self.package / "PKGBUILD").read_text()
        self.assertIn("epoch=1", recipe)
        for scheme in ("http", "https"):
            self.assertIn(f"{scheme}::/usr/bin/wget", recipe)
        self.assertIn("validpgpkeys=", recipe)
        self.assertIn("sha512sum -c", recipe)


class FritzingDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.package = Path(__file__).resolve().parents[1] / "packages" / "fritzing"
        self.config = far.read_config(self.package)
        self.recipe = (self.package / "PKGBUILD").read_text()
        self.head = "a" * 40
        self.bump = "b" * 40

    def fetch(self, url, config):
        import plistlib
        if url.endswith("FritzingInfo.plist"):
            return plistlib.dumps({"CFBundleShortVersionString": self.version})
        return f'<component><releases><release version="{self.version}"/></releases></component>'.encode()

    def history(self):
        return [{"sha": self.bump, "commit": {"message": "Bump version to 1.0.9"}},
                {"sha": "c" * 40, "commit": {"message": "Bump version to 1.0.8"}}]

    def test_current_source_version_keeps_pins_without_using_github_releases(self):
        self.version = "1.0.8"
        with patch.object(upstreams, "fetch", side_effect=self.fetch), \
                patch.object(upstreams, "request_json", return_value=[{"sha": self.head}]) as request, \
                patch.object(upstreams, "github_releases", side_effect=AssertionError("unused releases feed")):
            selected = upstreams.fritzing(self.config, self.recipe)
        upstream.validate_candidate(selected, self.config)
        self.assertEqual(selected["assignments"]["_gitrev"], far.assignment(self.recipe, "_gitrev"))
        self.assertEqual(request.call_count, 1)

    def test_new_source_version_selects_exact_bump_and_retains_parts(self):
        self.version = "1.0.9"
        with patch.object(upstreams, "fetch", side_effect=self.fetch), \
                patch.object(upstreams, "request_json", side_effect=[[{"sha": self.head}], self.history()]) as request:
            selected = upstreams.fritzing(self.config, self.recipe)
        upstream.validate_candidate(selected, self.config)
        self.assertEqual(selected["assignments"]["_gitrev"], self.bump)
        self.assertEqual(selected["assignments"]["_partsrev"], far.assignment(self.recipe, "_partsrev"))
        self.assertEqual(selected["release_url"], f"https://github.com/fritzing/fritzing-app/commit/{self.bump}")
        self.assertIn(f"sha={self.head}&path=src%2Fversion%2Fversion.cpp", request.call_args.args[0])

    def test_missing_or_ambiguous_version_bumps_require_manual_review(self):
        self.version = "1.0.9"
        ambiguous = [{"sha": "d" * 40, "commit": {"message": "Bump version to 1.0.9"}}, *self.history()]
        for history in ([], ambiguous):
            with patch.object(upstreams, "fetch", side_effect=self.fetch), \
                    patch.object(upstreams, "request_json", side_effect=[[{"sha": self.head}], history]):
                with self.assertRaisesRegex(far.MaintenanceError, "review source pins manually"):
                    upstreams.fritzing(self.config, self.recipe)

    def test_message_without_matching_appstream_metadata_is_rejected(self):
        self.version = "1.0.9"
        def fetch(url, config):
            if url.endswith(".xml"):
                return b'<component><releases><release version="1.0.8"/></releases></component>'
            return self.fetch(url, config)
        with patch.object(upstreams, "fetch", side_effect=fetch), \
                patch.object(upstreams, "request_json", side_effect=[[{"sha": self.head}], self.history()]):
            with self.assertRaisesRegex(far.MaintenanceError, "does not confirm"):
                upstreams.fritzing(self.config, self.recipe)


class UpstreamUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.package = Path(temporary.name) / "enpass-bin"
        shutil.copytree(Path(__file__).resolve().parents[1] / "packages/enpass-bin", self.package)
        self.config = far.read_config(self.package)
        self.original = (self.package / "PKGBUILD").read_text()
        self.metadata = (self.package / ".SRCINFO").read_bytes()

    def selected(self, version="6.12.7.2300"):
        payload = upstreams.source(self.config, "_url", f"https://apt.enpass.io/pool/main/e/enpass/enpass_{version}_amd64.deb",
                                   digest=DIGEST, size=len(PAYLOAD))
        return upstreams.candidate(self.config, version, self.config["release_url"], [payload])

    def test_applied_update_resets_pkgrel_and_is_idempotent(self):
        data = self.selected()
        with patch.object(upstreams, "discover", side_effect=lambda *args, **kwargs: copy.deepcopy(data)), \
                patch.object(upstream, "hash_source", return_value=DIGEST) as download, \
                patch.object(upstream, "generate_srcinfo", return_value="generated metadata\n"), \
                patch.object(upstream, "check_package"):
            result = far.update_one(self.package, apply=True)
            again = far.update_one(self.package, apply=True)
        self.assertEqual(result["status"], "updated")
        self.assertEqual(again["status"], "up-to-date")
        self.assertEqual(download.call_count, 1)
        self.assertEqual(far.assignment((self.package / "PKGBUILD").read_text(), "pkgrel"), "1")

    def test_failed_validation_rolls_back_recipe_and_metadata(self):
        for failure in ("generate_srcinfo", "check_package"):
            with patch.object(upstreams, "discover", return_value=self.selected()), \
                    patch.object(upstream, "hash_source", return_value=DIGEST), \
                    patch.object(upstream, "generate_srcinfo", return_value="new metadata\n"), \
                    patch.object(upstream, "check_package"), \
                    patch.object(upstream, failure, side_effect=far.MaintenanceError("fixture failure")):
                with self.assertRaisesRegex(far.MaintenanceError, "fixture failure"):
                    far.update_one(self.package, apply=True)
            self.assertEqual((self.package / "PKGBUILD").read_text(), self.original)
            self.assertEqual((self.package / ".SRCINFO").read_bytes(), self.metadata)

    def test_downgrade_and_same_version_mutation_are_rejected_before_download(self):
        for version in ("5.0.0", far.assignment(self.original, "pkgver")):
            with patch.object(upstreams, "discover", return_value=self.selected(version)), \
                    patch.object(upstream, "hash_source", side_effect=AssertionError("should not download")):
                with self.assertRaises(far.MaintenanceError):
                    far.update_one(self.package, apply=True)

    def test_no_configuration_tracks_aur(self):
        root = Path(__file__).resolve().parents[1]
        for package in far.package_paths(root=root):
            self.assertEqual(far.read_config(package)["source"], "upstream")

    def test_package_discovery_rejects_unknown_and_traversal_names(self):
        for name in ("../bambustudio-appimage", "missing", "bambustudio-appimage/PKGBUILD"):
            with self.assertRaises(far.MaintenanceError):
                far.package_paths([name])

    def test_makepkg_receives_no_automation_credentials(self):
        completed = subprocess.CompletedProcess([], 0, stdout=f"pkgbase = {self.package.name}\n", stderr="")
        with patch.dict(far.os.environ, {"GH_TOKEN": "fixture", "GITHUB_TOKEN": "fixture", "PRIVATE_KEY": "fixture"}), \
                patch.object(far.subprocess, "run", return_value=completed) as run:
            far.generate_srcinfo(self.package)
        self.assertFalse({"GH_TOKEN", "GITHUB_TOKEN", "PRIVATE_KEY"} & run.call_args.kwargs["env"].keys())

    def test_subprocess_failure_in_one_package_does_not_hide_others(self):
        failure = subprocess.CalledProcessError(1, ["vercmp"])
        results = [failure, {"package": "spotify", "status": "up-to-date", "version": "1"}]
        output = io.StringIO()
        with patch.object(sys, "argv", ["update-packages", "enpass-bin", "spotify"]), \
                patch.object(far, "update_one", side_effect=results), patch("sys.stdout", output):
            self.assertTrue(far.update_main())
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn('"status": "error"', lines[0])
        self.assertIn('"status": "up-to-date"', lines[1])


if __name__ == "__main__":
    unittest.main()
