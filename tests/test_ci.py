from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

from tests import run as test_runner


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


class BlenderAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = load_ci_module()

    def test_every_supported_platform_has_the_approved_archive_digest(self):
        expected = {
            "windows": (
                "blender-5.2.0-windows-x64.zip",
                "2d184b626c001692c362291911293b6a297179d618d95e9e9192c3a80318adc4",
            ),
            "linux": (
                "blender-5.2.0-linux-x64.tar.xz",
                "96f6c181a30f4950607839dc84d42a354b250d8a0231b098b59b7bc69c351c48",
            ),
            "macos": (
                "blender-5.2.0-macos-arm64.dmg",
                "ed4d8390166dec5ea0a2813a03db6221f206ce016442be7f59f41d760972568a",
            ),
        }
        self.assertEqual(
            expected,
            {
                key: (value["filename"], value["sha256"])
                for key, value in self.ci.PLATFORMS.items()
            },
        )

    def test_curl_requires_https_and_one_resolution_strategy(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            self.ci.curl_command("http://example.test/file", Path("file"))
        with self.assertRaisesRegex(ValueError, "choose"):
            self.ci.curl_command(
                "https://example.test/file",
                Path("file"),
                "https://resolver.test/dns-query",
                ("192.0.2.1",),
            )

    def test_dns_parser_rejects_truncated_message(self):
        with self.assertRaisesRegex(ValueError, "truncated"):
            self.ci._parse_dns_a_response(b"short", 1, b"question")

    def test_blender_version_is_exact(self):
        self.ci.require_blender_version("Blender 5.2.0 LTS")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.ci.require_blender_version("Blender 5.2.1")


class WorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (
            REPOSITORY_DIR / ".github" / "workflows" / "Cats Tests.yml"
        ).read_text(encoding="utf-8")

    def test_actions_are_immutable_and_checkout_drops_credentials(self):
        import re

        refs = re.findall(
            r"^\s*uses:\s*[^@\s]+@([^\s]+)$", self.workflow, re.MULTILINE
        )
        self.assertTrue(refs)
        self.assertTrue(
            all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs)
        )
        self.assertIn("persist-credentials: false", self.workflow)

    def test_matrix_and_trigger_policy(self):
        for value in ("windows-2025", "ubuntu-24.04", "macos-15"):
            self.assertIn(value, self.workflow)
        self.assertNotIn("schedule:", self.workflow)
        self.assertNotIn("forked_dev", self.workflow)
        self.assertNotIn("actions/setup-python", self.workflow)
        self.assertIn("permissions:\n  contents: read", self.workflow)

    def test_explicit_compile_paths_replace_repository_dot(self):
        self.assertNotIn("compileall -q -f .", self.workflow)
        for path in (
            "__init__.py",
            "globs.py",
            "extentions.py",
            "updater.py",
            "tools",
            "ui",
            "extern_tools",
            "tests",
        ):
            self.assertIn(path, self.workflow)


class FixtureSecurityTests(unittest.TestCase):
    def test_canonical_asset_hashes_are_committed(self):
        self.assertEqual(
            {
                "armatures/armature.ryuko.blend": (
                    "d92b918968e7d0f2d06ef75ba739b85091fc5409954d2dcd880aed21af09a6db"
                ),
                "armatures/armature.bonetranslationerror.blend": (
                    "1b4c3e2cd02a5bd611c44aa8261f6a45c07f67cbb81d7e09cbe3ff85dc788014"
                ),
                "shapekeys/shapekey.shape_key_to_basis.blend": (
                    "a596211cfcd3c6bdd7b1b78218de2940b9c9b8f96b756374a9a1a55b73df8223"
                ),
            },
            {asset.relative_path: asset.sha256 for asset in test_runner.TEST_ASSETS},
        )

    def test_copy_limited_rejects_oversize_input(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "asset.part"
            with target.open("wb") as output:
                with self.assertRaisesRegex(RuntimeError, "size limit"):
                    test_runner.copy_limited(io.BytesIO(b"12345"), output, 4)

    def test_verify_asset_rejects_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "asset.blend"
            target.write_bytes(b"BLENDER-corrupt")
            asset = test_runner.TestAsset(
                "asset.blend", "https://example.test", "0" * 64
            )
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                test_runner.verify_asset(target, asset)

    def test_blender_command_disables_autoexec(self):
        command = test_runner.blender_command(
            "blender", Path("a.blend"), Path("t.py")
        )
        self.assertIn("--disable-autoexec", command)
        self.assertIn("--offline-mode", command)


if __name__ == "__main__":
    unittest.main()
