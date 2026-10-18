"""Direct upstream integrity checks; no network or package builds."""

import hashlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import far
import far_upstream as upstream

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


if __name__ == "__main__":
    unittest.main()
