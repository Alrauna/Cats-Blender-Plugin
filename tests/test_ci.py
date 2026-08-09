from __future__ import annotations

import importlib.util
import io
import re
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


def workflow_job(workflow: str, name: str) -> str:
    match = re.search(
        rf"^  {re.escape(name)}:\n(?P<body>.*?)(?=^  [a-z][a-z0-9_]*:\n|\Z)",
        workflow,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"workflow job is missing: {name}")
    return match.group("body")


def job_permissions(block: str) -> set[str]:
    match = re.search(
        r"^    permissions:\n(?P<body>(?:^      [a-z-]+: (?:read|write)\n)+)",
        block,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError("job permissions are missing")
    return {line.strip() for line in match.group("body").splitlines()}


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

    def test_fixture_runner_uses_host_python_certificate_store(self):
        self.assertEqual(2, self.workflow.count("python tests/run.py"))
        self.assertNotIn(
            "${{ steps.blender.outputs.python }}' tests/run.py", self.workflow
        )

    def test_release_jobs_isolate_write_tokens_from_actions(self):
        draft = workflow_job(self.workflow, "draft_release")
        attest = workflow_job(self.workflow, "attest_release")
        publish = workflow_job(self.workflow, "publish_release")

        self.assertEqual({"contents: write"}, job_permissions(draft))
        self.assertEqual(
            {"contents: read", "id-token: write", "attestations: write"},
            job_permissions(attest),
        )
        self.assertEqual({"contents: write"}, job_permissions(publish))
        self.assertNotIn("uses:", draft)
        self.assertNotIn("uses:", publish)
        self.assertEqual(
            ["actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"],
            re.findall(r"^\s*uses:\s*([^\s]+)$", attest, re.MULTILINE),
        )
        self.assertEqual(1, self.workflow.count("id-token: write"))
        self.assertEqual(1, self.workflow.count("attestations: write"))
        self.assertEqual(2, self.workflow.count("contents: write"))
        self.assertIn("environment: release", draft)
        self.assertNotIn("environment:", attest)
        self.assertIn("environment: release", publish)

    def test_release_jobs_bind_and_reverify_the_stored_primary_zip(self):
        draft = workflow_job(self.workflow, "draft_release")
        attest = workflow_job(self.workflow, "attest_release")
        publish = workflow_job(self.workflow, "publish_release")

        self.assertIn("needs: [validate, release_gate]", draft)
        self.assertIn("needs: draft_release", attest)
        self.assertIn("needs: [draft_release, attest_release]", publish)
        outputs = re.search(
            r"^    outputs:\n(?P<body>(?:^      [a-z0-9_]+: .+\n)+)",
            draft,
            re.MULTILINE,
        )
        self.assertIsNotNone(outputs)
        output_names = set(
            re.findall(
                r"^      ([a-z0-9_]+):", outputs.group("body"), re.MULTILINE
            )
        )
        self.assertEqual(
            {"tag", "archive_name", "sha256", "release_id", "asset_id"},
            output_names,
        )
        for output in (
            "tag",
            "archive_name",
            "sha256",
            "release_id",
            "asset_id",
        ):
            self.assertIn(f"      {output}: ${{{{ steps.", draft)
            self.assertIn(f"needs.draft_release.outputs.{output}", attest)
            self.assertIn(f"needs.draft_release.outputs.{output}", publish)
        self.assertIn("releases/assets/${ASSET_ID}", attest)
        self.assertIn("releases/assets/${ASSET_ID}", publish)
        self.assertIn("sha256sum", attest)
        self.assertIn("sha256sum", publish)
        self.assertLess(
            draft.index('[[ "${release_id}" =~ ^[0-9]+$ ]]'),
            draft.index("releases/${release_id}"),
        )
        self.assertLess(
            draft.index('[[ "${asset_id}" =~ ^[0-9]+$ ]]'),
            draft.index("releases/assets/${asset_id}"),
        )
        for block in (attest, publish):
            self.assertLess(
                block.index('[[ "${RELEASE_ID}" =~ ^[0-9]+$ ]]'),
                block.index("releases/${RELEASE_ID}"),
            )
            self.assertLess(
                block.index('[[ "${ASSET_ID}" =~ ^[0-9]+$ ]]'),
                block.index("releases/assets/${ASSET_ID}"),
            )
        self.assertIn(
            "subject-path: '${{ runner.temp }}/stored-release/"
            "${{ needs.draft_release.outputs.archive_name }}'",
            attest,
        )
        self.assertEqual(1, attest.count("subject-path:"))
        self.assertNotIn("subject-checksums:", attest)
        self.assertIn("releases/${RELEASE_ID}", publish)
        self.assertIn("-F draft=false", publish)
        self.assertLess(
            attest.index('test "${actual_sha256}" = "${EXPECTED_SHA256}"'),
            attest.index("uses: actions/attest@"),
        )
        self.assertLess(
            publish.index('test "${actual_sha256}" = "${EXPECTED_SHA256}"'),
            publish.index("-F draft=false"),
        )
        self.assertNotIn("actions/upload-artifact", draft + attest + publish)
        self.assertNotIn("actions/download-artifact", draft + attest + publish)

    def test_release_is_manual_public_main_only_and_validation_gated(self):
        condition_parts = (
            "github.event_name == 'workflow_dispatch'",
            "inputs.release != ''",
            "github.ref == 'refs/heads/main'",
            "github.event.repository.visibility == 'public'",
        )
        draft = workflow_job(self.workflow, "draft_release")
        attest = workflow_job(self.workflow, "attest_release")
        publish = workflow_job(self.workflow, "publish_release")
        for block in (draft, attest, publish):
            for condition in condition_parts:
                self.assertIn(condition, block)
        self.assertIn("needs: [validate, release_gate]", draft)
        self.assertIn("EXPECTED_SHA: ${{ github.sha }}", draft)
        self.assertIn(
            'test "$(git rev-parse HEAD)" = "${EXPECTED_SHA}"', draft
        )
        self.assertIn("SHA256SUMS.txt", draft)
        self.assertIn("--draft", draft)


class ReleaseCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = load_ci_module()

    def test_prepare_release_writes_expected_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "blender_manifest.toml"
            archive = root / "cats_blender_plugin-5.2.2.zip"
            sums = root / "SHA256SUMS.txt"
            output = root / "github-output.txt"
            manifest.write_text(
                'id = "cats_blender_plugin"\nversion = "5.2.2"\n',
                encoding="utf-8",
            )
            archive.write_bytes(b"package")
            self.assertEqual(
                0,
                self.ci.main(
                    [
                        "prepare-release",
                        "--version",
                        "5.2.2",
                        "--manifest",
                        str(manifest),
                        "--archive",
                        str(archive),
                        "--checksum-output",
                        str(sums),
                        "--github-output",
                        str(output),
                    ]
                ),
            )
            written = output.read_text("utf-8")
            self.assertIn("tag=v5.2.2\n", written)
            self.assertIn(
                "archive_name=cats_blender_plugin-5.2.2.zip\n", written
            )
            self.assertRegex(written, r"sha256=[0-9a-f]{64}\n")

    def test_prepare_release_rejects_wrong_archive_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "blender_manifest.toml"
            archive = root / "wrong.zip"
            manifest.write_text(
                'id = "cats_blender_plugin"\nversion = "5.2.2"\n',
                encoding="utf-8",
            )
            archive.write_bytes(b"package")
            with self.assertRaisesRegex(ValueError, "must be named"):
                self.ci.main(
                    [
                        "prepare-release",
                        "--version",
                        "5.2.2",
                        "--manifest",
                        str(manifest),
                        "--archive",
                        str(archive),
                        "--checksum-output",
                        str(root / "SHA256SUMS.txt"),
                        "--github-output",
                        str(root / "github-output.txt"),
                    ]
                )

    def test_verify_file_rejects_stored_file_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "stored.zip"
            archive.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                self.ci.main(
                    [
                        "verify-file",
                        "--file",
                        str(archive),
                        "--expected-sha256",
                        "0" * 64,
                    ]
                )


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
