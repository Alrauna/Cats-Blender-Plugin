from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


REPOSITORY_DIR = Path(__file__).resolve().parent.parent
CI_SCRIPT = REPOSITORY_DIR / "scripts" / "ci.py"


def load_ci_module():
    spec = importlib.util.spec_from_file_location("cats_ci", CI_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load scripts/ci.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CiPrimitiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = load_ci_module()

    def test_checksum_manifest_is_strict_and_unique(self):
        digest = "a" * 64
        self.assertEqual(
            {"blender.zip": digest},
            self.ci.parse_checksum_manifest(
                f"{digest}  blender.zip\n".encode("utf-8")
            ),
        )
        with self.assertRaisesRegex(ValueError, "malformed"):
            self.ci.parse_checksum_manifest(b"not-a-checksum blender.zip\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.ci.parse_checksum_manifest(
                f"{digest}  blender.zip\n{digest}  blender.zip\n".encode()
            )

    def test_consensus_requires_three_identical_official_payloads(self):
        digest = "b" * 64
        payload = f"{digest}  blender.zip\n".encode()
        self.ci.require_checksum_consensus(
            (payload, payload, payload), "blender.zip", digest
        )
        with self.assertRaisesRegex(ValueError, "disagree"):
            self.ci.require_checksum_consensus(
                (payload, payload, payload + b"\n"), "blender.zip", digest
            )
        with self.assertRaisesRegex(ValueError, "committed"):
            self.ci.require_checksum_consensus(
                (payload, payload, payload), "blender.zip", "c" * 64
            )

    def test_release_identity_accepts_final_version_only(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "blender_manifest.toml"
            manifest.write_text(
                'id = "cats_blender_plugin"\nversion = "5.2.2"\n',
                encoding="utf-8",
            )
            self.assertEqual(
                ("v5.2.2", "cats_blender_plugin-5.2.2.zip"),
                self.ci.release_identity("5.2.2", manifest),
            )
            with self.assertRaisesRegex(ValueError, "X.Y.Z"):
                self.ci.release_identity("5.2.2-beta.1", manifest)
            with self.assertRaisesRegex(ValueError, "does not match"):
                self.ci.release_identity("5.2.3", manifest)

    def test_github_output_rejects_line_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output.txt"
            with self.assertRaisesRegex(ValueError, "single-line"):
                self.ci.write_github_output(output, archive="safe\nforged=value")

    def test_file_digest_round_trip_and_malformed_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.zip"
            sums = Path(directory) / "SHA256SUMS.txt"
            path.write_bytes(b"verified release")
            digest = self.ci.write_sha256s(path, sums)
            self.ci.require_file_sha256(path, digest)
            self.assertEqual(f"{digest}  asset.zip\n", sums.read_text("utf-8"))
            with self.assertRaisesRegex(ValueError, "malformed"):
                self.ci.require_file_sha256(path, "short")


if __name__ == "__main__":
    unittest.main()
