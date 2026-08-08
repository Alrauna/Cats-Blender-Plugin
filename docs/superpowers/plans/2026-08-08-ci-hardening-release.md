# CI Hardening and Manual Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Secure every external CI input, validate the universal CATS package on Windows, Linux, and macOS Apple Silicon, remove dead CI-only files, and add manual publication of checksum-verified final releases.

**Architecture:** Keep `.github/workflows/Cats Tests.yml` as the single workflow and add one standard-library helper, `scripts/ci.py`, for trusted Blender acquisition and release identity/checksums. Preserve CATS' existing package and runtime gates, extend `tests/run.py` to authenticate retained fixtures, and permit release publication only after a fresh three-platform matrix succeeds.

**Tech Stack:** Python 3 standard library, `unittest`, Blender 5.2.0 LTS command-line extension tooling, GitHub Actions, Bash, PowerShell/`hdiutil` on macOS, GitHub CLI in the release job.

## Global Constraints

- Work only on `codex/ci-hardening-release`, based on `main` commit `b4e36f73797a7d9ff66d46f0702200478a259a73`.
- Target exactly Blender `5.2.0 LTS` on `windows-2025`, `ubuntu-24.04`, and `macos-15` Apple Silicon.
- Keep the flat repository root as the Blender extension package root.
- Keep `docs/`, `scripts/`, and `tests/` excluded by `blender_manifest.toml` and rejected by `tests/verify_package.py`.
- Add no Python dependency, cache, linter, reusable workflow, split-platform package, scheduled trigger, automatic publication, dry-run release, or prerelease publication.
- Preserve every current CATS source, package, install, smoke, lifecycle, armature, shape-key, removal, and absence gate.
- Use an optional manual `release` input; only exact final `X.Y.Z` values on public `main` may publish.
- Pin every GitHub Action to a full 40-character commit SHA and set checkout `persist-credentials: false`.
- Treat resolver disagreement, checksum drift, malformed input, unsafe extraction, and stored-asset mismatch as fatal.
- Do not modify `.local-references/`, `.packaged-releases/`, `.test-runtime/`, retained fixtures, updater URLs, version metadata, or bundled MMD behavior.
- Use test-driven development for every behavior change and `git diff --check` before every commit.
- Stage explicit paths only; do not stage ignored or unrelated files.

## File map

- Create `scripts/ci.py`: checksum consensus, independent DNS resolution, verified Blender acquisition, final-release identity, release checksums, and CLI.
- Create `tests/test_ci.py`: standard-library unit tests for `scripts/ci.py`, fixture authentication helpers, and immutable workflow policy.
- Modify `tests/run.py`: pinned fixture hashes, bounded downloads, existing-file authentication, and `--disable-autoexec`.
- Modify `.github/workflows/Cats Tests.yml`: immutable actions, three-platform matrix, preserved CATS gates, and manual release jobs.
- Delete `tests/termcolor.py`: unused vendored output helper.
- Delete `tests/old/copy_protection.test.py`, `tests/old/translate.test.py`, and `tests/old/viseme.test.py`: uninvoked obsolete probes.
- Modify `docs/HANDOFF.md`: record the completed branch, validation, remaining external release check, and recommended next action.
- Delete the in-flight design and plan in the final milestone commit after implementation and verification; Git history retains both.

---

### Task 1: Checksum, release-identity, and output primitives

**Files:**
- Create: `scripts/ci.py`
- Create: `tests/test_ci.py`

**Interfaces:**
- Produces: `sha256_file(path: Path) -> str`
- Produces: `parse_checksum_manifest(payload: bytes) -> dict[str, str]`
- Produces: `require_checksum_consensus(payloads: tuple[bytes, bytes, bytes], filename: str, expected_sha256: str) -> None`
- Produces: `write_github_output(path: Path | None, **values: str | Path) -> None`
- Produces: `release_identity(version: str, manifest: Path) -> tuple[str, str]`
- Produces: `write_sha256s(archive: Path, output: Path) -> str`
- Produces: `require_file_sha256(path: Path, expected_sha256: str) -> None`

- [ ] **Step 1: Create the RED unit-test loader and primitive tests**

Create `tests/test_ci.py` with a loader that imports the repository-only script directly and tests strict behavior:

```python
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
```

- [ ] **Step 2: Run the primitive tests to verify RED**

Run:

```powershell
python -m unittest tests.test_ci.CiPrimitiveTests -v
```

Expected: FAIL because `scripts/ci.py` does not exist.

- [ ] **Step 3: Implement the minimum primitive module**

Create `scripts/ci.py` with SPDX header `GPL-3.0-or-later`, standard-library imports, strict regular expressions, and these implementations:

```python
from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_checksum_manifest(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode("utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not SHA256_PATTERN.fullmatch(parts[0].lower()):
            raise ValueError(f"malformed checksum row: {line!r}")
        digest, filename = parts[0].lower(), parts[1].removeprefix("*")
        if filename in result:
            raise ValueError(f"duplicate checksum entry: {filename}")
        result[filename] = digest
    if not result:
        raise ValueError("empty checksum manifest")
    return result


def require_checksum_consensus(
    payloads: tuple[bytes, bytes, bytes],
    filename: str,
    expected_sha256: str,
) -> None:
    if len(set(payloads)) != 1:
        raise ValueError("resolver checksum payloads disagree")
    published = parse_checksum_manifest(payloads[0]).get(filename)
    if published is None:
        raise ValueError(f"checksum entry is missing: {filename}")
    if published != expected_sha256:
        raise ValueError("official checksum disagrees with committed checksum")


def write_github_output(path: Path | None, **values: str | Path) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            text = str(value)
            if "\n" in text or "\r" in text:
                raise ValueError(f"GitHub output must be single-line: {key}")
            stream.write(f"{key}={text}\n")


def release_identity(version: str, manifest: Path) -> tuple[str, str]:
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"release version must use X.Y.Z: {version!r}")
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    if data["version"] != version:
        raise ValueError(
            f"manifest version {data['version']!r} does not match {version!r}"
        )
    return f"v{version}", f"{data['id']}-{version}.zip"


def write_sha256s(archive: Path, output: Path) -> str:
    digest = sha256_file(archive)
    output.write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n"
    )
    return digest


def require_file_sha256(path: Path, expected_sha256: str) -> None:
    if not SHA256_PATTERN.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 is malformed")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(
            f"file SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )
```

- [ ] **Step 4: Run the primitive tests to verify GREEN**

Run:

```powershell
python -m unittest tests.test_ci.CiPrimitiveTests -v
python -W ignore::SyntaxWarning -m compileall -q -f scripts/ci.py tests/test_ci.py
git diff --check
```

Expected: all primitive tests pass; compilation and diff check exit 0.

- [ ] **Step 5: Commit the primitive security contract**

```powershell
git add -- scripts/ci.py tests/test_ci.py
git diff --cached --check
git commit -m "test: define CI trust-boundary primitives"
```

---

### Task 2: Independent resolver consensus and verified Blender acquisition

**Files:**
- Modify: `scripts/ci.py`
- Modify: `tests/test_ci.py`

**Interfaces:**
- Consumes: Task 1 checksum and GitHub-output functions.
- Produces: `curl_command(url: str, output: Path, doh_url: str | None = None, resolved_addresses: tuple[str, ...] | None = None) -> list[str]`
- Produces: `_decode_dns_name(...)`, `_parse_dns_a_response(...)`, and `quad9_addresses(hostname: str) -> tuple[str, ...]`
- Produces: `extract_archive(platform: str, archive: Path, destination: Path) -> None`
- Produces: `prepare_blender(platform: str, output_dir: Path, github_output: Path | None = None) -> tuple[Path, Path]`

- [ ] **Step 1: Add RED tests for platform pins, download policy, DNS rejection, and version checks**

Extend `tests/test_ci.py` with `BlenderAcquisitionTests`. Assert the exact three filenames and digests from the spec, HTTPS-only curl construction, rejection of mixed DoH/addresses, malformed DNS rejection, exact version matching, and single-line outputs:

```python
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
```

- [ ] **Step 2: Run acquisition tests to verify RED**

```powershell
python -m unittest tests.test_ci.BlenderAcquisitionTests -v
```

Expected: FAIL because platform metadata, DNS, curl, and version functions do not exist.

- [ ] **Step 3: Port the approved hardened acquisition implementation**

Adapt the exact bounds and parser flow from the approved companion sources:

- `Alrauna/blender-alpha-material-separator/scripts/ci.py` for Windows/Linux DNS consensus and extraction.
- `Alrauna/material-combiner-addon/tools/ci.py` for macOS metadata, read-only DMG attachment, plist parsing, application-bundle copy, and guaranteed detach.

Keep these exact constants and orchestration in `scripts/ci.py`:

```python
BLENDER_VERSION = "5.2.0"
BASE_URL = "https://download.blender.org/release/Blender5.2"
CHECKSUM_URL = f"{BASE_URL}/blender-{BLENDER_VERSION}.sha256"
CLOUDFLARE_DOH_URL = "https://cloudflare-dns.com/dns-query"
QUAD9_DOT_HOST = "dns.quad9.net"
QUAD9_DOT_PORT = 853
MAX_RESOLVED_ADDRESSES = 16
CONNECT_TIMEOUT_SECONDS = 30
TOTAL_TIMEOUT_SECONDS = 900
PROCESS_TIMEOUT_SECONDS = 960
RETRIES = 2
```

Use the three exact platform dictionaries from the RED test. Implement
`_read_exact`, `_decode_dns_name`, `_parse_dns_a_response`, and
`quad9_addresses` with the companion bounds: one question, standard opcode,
no truncation/error flags, valid compression pointers only, labels at most 63
bytes, expanded names at most 255 bytes, IPv4 A records only, owner equal to
the question, and at most 16 unique addresses.

Build curl commands with `--proto =https`, TLS 1.2 minimum, no redirects,
bounded timeouts, two retries, HTTP-status output, optional Cloudflare
`--doh-url`, and optional Quad9 `--resolve`. Delete the output after timeout,
nonzero curl status, or non-200 HTTP status.

Implement the top-level acquisition flow exactly as:

```python
def prepare_blender(
    platform: str,
    output_dir: Path,
    github_output: Path | None = None,
) -> tuple[Path, Path]:
    metadata = PLATFORMS[platform]
    output_dir.mkdir(parents=True, exist_ok=False)
    checksum_paths = tuple(output_dir / f"checksums-{i}.txt" for i in range(3))
    download(CHECKSUM_URL, checksum_paths[0])
    download(CHECKSUM_URL, checksum_paths[1], doh_url=CLOUDFLARE_DOH_URL)
    download(
        CHECKSUM_URL,
        checksum_paths[2],
        resolved_addresses=quad9_addresses("download.blender.org"),
    )
    payloads = tuple(path.read_bytes() for path in checksum_paths)
    require_checksum_consensus(
        payloads, metadata["filename"], metadata["sha256"]
    )
    archive = output_dir / metadata["filename"]
    download(f"{BASE_URL}/{metadata['filename']}", archive)
    require_file_sha256(archive, metadata["sha256"])
    extracted = output_dir / "blender"
    extract_archive(platform, archive, extracted)
    blender, python = locate_blender_and_python(platform, extracted)
    reported = subprocess.run(
        [str(blender), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0].strip()
    require_blender_version(reported)
    write_github_output(github_output, blender=blender, python=python)
    return blender, python
```

For Linux call `shutil.unpack_archive(..., filter="data")`. For Windows call
`shutil.unpack_archive` only after the committed hash passes. For macOS use
`hdiutil attach -nobrowse -readonly -plist`, require one mount point, copy
`Blender.app` with `symlinks=True`, and call `hdiutil detach` in `finally`.

- [ ] **Step 4: Add the CLI parser for `prepare-blender` only**

Add `_parser()` and `main()` with the exact arguments:

```python
prepare = subparsers.add_parser("prepare-blender")
prepare.add_argument("--platform", choices=tuple(PLATFORMS), required=True)
prepare.add_argument("--output-dir", type=Path, required=True)
prepare.add_argument("--github-output", type=Path)
```

Dispatch it to `prepare_blender` and return 0.

- [ ] **Step 5: Run acquisition tests and a local non-network CLI check**

```powershell
python -m unittest tests.test_ci.BlenderAcquisitionTests -v
python scripts/ci.py --help
python scripts/ci.py prepare-blender --help
python -W ignore::SyntaxWarning -m compileall -q -f scripts/ci.py tests/test_ci.py
git diff --check
```

Expected: tests pass; both help commands exit 0; compilation and diff check pass. Do not download Blender during this unit task.

- [ ] **Step 6: Commit verified Blender acquisition**

```powershell
git add -- scripts/ci.py tests/test_ci.py
git diff --cached --check
git commit -m "feat: verify Blender before CI execution"
```

---

### Task 3: Authenticate and bound retained test assets

**Files:**
- Modify: `tests/run.py:33-65,175-198,212-224`
- Modify: `tests/test_ci.py`

**Interfaces:**
- Produces: `TestAsset(relative_path: str, url: str, sha256: str)`
- Produces: `sha256_file(path: Path) -> str` in `tests/run.py`
- Produces: `verify_asset(path: Path, asset: TestAsset) -> None`
- Produces: `copy_limited(source, destination, max_bytes: int) -> None`
- Preserves: existing `download_asset(asset, timeout)` and test-runner CLI.

- [ ] **Step 1: Add RED fixture tests**

Load `tests.run` normally and add tests using `io.BytesIO`, temporary files,
and a test-specific byte ceiling:

```python
import io
from tests import run as test_runner


class FixtureSecurityTests(unittest.TestCase):
    def test_canonical_asset_hashes_are_committed(self):
        self.assertEqual(
            {
                "armatures/armature.ryuko.blend":
                    "d92b918968e7d0f2d06ef75ba739b85091fc5409954d2dcd880aed21af09a6db",
                "armatures/armature.bonetranslationerror.blend":
                    "1b4c3e2cd02a5bd611c44aa8261f6a45c07f67cbb81d7e09cbe3ff85dc788014",
                "shapekeys/shapekey.shape_key_to_basis.blend":
                    "a596211cfcd3c6bdd7b1b78218de2940b9c9b8f96b756374a9a1a55b73df8223",
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
            asset = test_runner.TestAsset("asset.blend", "https://example.test", "0" * 64)
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                test_runner.verify_asset(target, asset)

    def test_blender_command_disables_autoexec(self):
        command = test_runner.blender_command("blender", Path("a.blend"), Path("t.py"))
        self.assertIn("--disable-autoexec", command)
        self.assertIn("--offline-mode", command)
```

- [ ] **Step 2: Run fixture tests to verify RED**

```powershell
python -m unittest tests.test_ci.FixtureSecurityTests -v
```

Expected: FAIL because hashes and helper functions are absent.

- [ ] **Step 3: Implement exact fixture pins and bounded streaming**

Add `hashlib`, set `MAX_TEST_ASSET_BYTES = 256 * 1024 * 1024`, add the three
digests from the test, and implement:

```python
def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_asset(path: Path, asset: TestAsset) -> None:
    actual = sha256_file(path)
    if actual != asset.sha256:
        raise RuntimeError(
            f"Test asset SHA-256 mismatch for {path}: expected {asset.sha256}, got {actual}"
        )
    magic = read_blender_file_magic(path)
    if magic != BLENDER_FILE_MAGIC:
        raise RuntimeError(f"Test asset is not a Blender file: {path}")


def copy_limited(source, destination, max_bytes: int) -> None:
    copied = 0
    while block := source.read(1024 * 1024):
        copied += len(block)
        if copied > max_bytes:
            raise RuntimeError(f"Test asset exceeds {max_bytes}-byte size limit")
        destination.write(block)
```

Change `download_asset` so existing files call `verify_asset`; downloads use
`copy_limited`, then `verify_asset(temporary, asset)`, then atomic replace.
Keep `.part` deletion in `finally`. Insert `--disable-autoexec` in
`blender_command` immediately after `--background`.

- [ ] **Step 4: Run fixture tests and retained runner parsing**

```powershell
python -m unittest tests.test_ci.FixtureSecurityTests -v
python tests/run.py --help
python -W ignore::SyntaxWarning -m compileall -q -f tests/run.py tests/test_ci.py
git diff --check
```

Expected: all tests pass and runner help remains valid.

- [ ] **Step 5: Verify the ignored canonical files against committed pins**

```powershell
Get-FileHash -Algorithm SHA256 `
  tests/armatures/armature.ryuko.blend, `
  tests/armatures/armature.bonetranslationerror.blend, `
  tests/shapekeys/shapekey.shape_key_to_basis.blend
```

Expected: the three hashes exactly match `TEST_ASSETS`. Do not stage these ignored files.

- [ ] **Step 6: Commit fixture authentication**

```powershell
git add -- tests/run.py tests/test_ci.py
git diff --cached --check
git commit -m "test: authenticate Blender fixture downloads"
```

---

### Task 4: Three-platform immutable validation workflow

**Files:**
- Modify: `.github/workflows/Cats Tests.yml`
- Modify: `tests/test_ci.py`

**Interfaces:**
- Consumes: `python scripts/ci.py prepare-blender --platform ...` from Task 2.
- Consumes: authenticated `tests/run.py` from Task 3.
- Produces: matrix outputs `steps.blender.outputs.blender` and `steps.blender.outputs.python`.
- Produces: platform-qualified tested package artifacts.

- [ ] **Step 1: Add RED workflow-policy tests**

Add a `WorkflowPolicyTests` class that reads the workflow as text and asserts
the stable security contract without introducing a YAML dependency:

```python
class WorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (
            REPOSITORY_DIR / ".github" / "workflows" / "Cats Tests.yml"
        ).read_text(encoding="utf-8")

    def test_actions_are_immutable_and_checkout_drops_credentials(self):
        import re
        refs = re.findall(r"^\s*uses:\s*[^@\s]+@([^\s]+)$", self.workflow, re.MULTILINE)
        self.assertTrue(refs)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs))
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
            "__init__.py", "globs.py", "extentions.py", "updater.py",
            "tools", "ui", "extern_tools", "tests",
        ):
            self.assertIn(path, self.workflow)
```

- [ ] **Step 2: Run workflow-policy tests to verify RED**

```powershell
python -m unittest tests.test_ci.WorkflowPolicyTests -v
```

Expected: FAIL on mutable action tags, missing matrix, schedule, stale branches, setup-python, and `compileall .`.

- [ ] **Step 3: Replace triggers, concurrency, and runner with the approved matrix**

Use these exact workflow controls:

```yaml
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      release:
        description: Publish final X.Y.Z release; leave empty for validation only
        required: false
        type: string

permissions:
  contents: read

concurrency:
  group: cats-blender-5-2-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

Set `strategy.fail-fast: false` and include the three runner/platform pairs.
Pin checkout to
`actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` with
`persist-credentials: false`. Remove `actions/setup-python` and the raw curl
Blender download.

- [ ] **Step 4: Wire verified Blender and preserve every CATS gate**

Use Bash on every matrix runner and call:

```yaml
- name: Verify and extract Blender 5.2.0
  id: blender
  shell: bash
  run: >-
    python scripts/ci.py prepare-blender
    --platform '${{ matrix.platform }}'
    --output-dir '${{ runner.temp }}/blender-5.2.0'
    --github-output "$GITHUB_OUTPUT"
```

Change syntax checking to the verified Python and exact source paths. Change
all Blender commands to `${{ steps.blender.outputs.blender }}` and all host
test-runner invocations to `${{ steps.blender.outputs.python }}`. Preserve the
current order and arguments for:

1. Source validation.
2. Build to `${{ runner.temp }}/cats_blender_plugin.zip`.
3. ZIP validation and `tests/verify_package.py`.
4. Isolated extension repository/profile creation.
5. Install and enable.
6. `extension_smoke.py --expect-enabled`.
7. `blender_52_api_smoke.py`.
8. `pose_mode_smoke.py`.
9. `overdraw_smoke.py`.
10. `import_sweep.py`.
11. `lifecycle_stress.py`.
12. Armature runner.
13. Shape-key runner.
14. Extension removal.
15. `extension_smoke.py --expect-absent`.

Pin artifact upload to
`actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`
and name each artifact `cats-blender-plugin-${{ matrix.platform }}-5.2.0`.

- [ ] **Step 5: Run policy tests and local Windows CI-equivalent checks**

```powershell
python -m unittest tests.test_ci -v
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --version
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --command extension validate .
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
git diff --check
```

Expected: unit tests pass, Blender reports `Blender 5.2.0 LTS`, source validation and compilation exit 0.

- [ ] **Step 6: Commit three-platform validation**

```powershell
git add -- '.github/workflows/Cats Tests.yml' tests/test_ci.py
git diff --cached --check
git commit -m "ci: validate CATS on three platforms"
```

---

### Task 5: Final-release CLI and manual publication jobs

**Files:**
- Modify: `scripts/ci.py`
- Modify: `tests/test_ci.py`
- Modify: `.github/workflows/Cats Tests.yml`

**Interfaces:**
- Consumes: Task 1 release/checksum functions and Task 2 Blender acquisition.
- Produces CLI commands `check-release`, `prepare-release`, and `verify-file`.
- Produces workflow outputs `tag`, `archive_name`, and `sha256`.

- [ ] **Step 1: Add RED CLI-dispatch tests**

Patch `sys.argv` or call `main([...])` directly after changing the signature to
`main(argv: list[str] | None = None) -> int`. Test exact final-version output,
archive-name rejection, and stored-file verification:

```python
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
            self.assertEqual(0, self.ci.main([
                "prepare-release", "--version", "5.2.2",
                "--manifest", str(manifest), "--archive", str(archive),
                "--checksum-output", str(sums), "--github-output", str(output),
            ]))
            written = output.read_text("utf-8")
            self.assertIn("tag=v5.2.2\n", written)
            self.assertIn("archive_name=cats_blender_plugin-5.2.2.zip\n", written)
            self.assertRegex(written, r"sha256=[0-9a-f]{64}\n")
```

- [ ] **Step 2: Run release CLI tests to verify RED**

```powershell
python -m unittest tests.test_ci.ReleaseCliTests -v
```

Expected: FAIL because the release subcommands are not registered.

- [ ] **Step 3: Complete the CLI parser and dispatch**

Add exact parsers for the three commands from the spec. In
`prepare-release`, require `archive.name == release_identity(...)[1]`, write
`SHA256SUMS.txt`, and emit `tag`, `archive_name`, and `sha256`. In
`verify-file`, call `require_file_sha256`. In `check-release`, call
`release_identity` only. Return 0 after successful dispatch.

- [ ] **Step 4: Add RED static release-policy assertions**

Extend `WorkflowPolicyTests`:

```python
def test_release_is_manual_main_only_and_write_scoped(self):
    self.assertIn("github.event_name == 'workflow_dispatch'", self.workflow)
    self.assertIn("github.ref == 'refs/heads/main'", self.workflow)
    self.assertIn("github.event.repository.visibility == 'public'", self.workflow)
    self.assertIn("environment: release", self.workflow)
    self.assertIn("contents: write", self.workflow)
    self.assertIn("needs: [validate, release_gate]", self.workflow)
    self.assertIn("SHA256SUMS.txt", self.workflow)
    self.assertIn("--draft", self.workflow)
    self.assertIn("Download and verify stored ZIP", self.workflow)
```

- [ ] **Step 5: Run release policy test to verify RED**

```powershell
python -m unittest tests.test_ci.WorkflowPolicyTests.test_release_is_manual_main_only_and_write_scoped -v
```

Expected: FAIL because release jobs are absent.

- [ ] **Step 6: Add the fast release gate**

Add `release_gate` on `ubuntu-24.04`, conditioned on non-empty manual release,
public `main`, with a pinned credential-free checkout. Set
`RELEASE_VERSION: ${{ inputs.release }}` and run:

```yaml
python scripts/ci.py check-release
--version "$RELEASE_VERSION"
--manifest blender_manifest.toml
```

- [ ] **Step 7: Add the release job with exact public-source and draft flow**

Add `release` with the identical condition, `needs: [validate, release_gate]`,
`runs-on: windows-2025`, `environment: release`, and job-only
`permissions.contents: write`.

Implement these exact steps in order:

1. `git init`, add public `https://github.com/${{ github.repository }}.git`,
   fetch `${{ github.sha }}` without tags/credentials, checkout detached, and
   compare `git rev-parse HEAD` to `${{ github.sha }}`.
2. Run `python scripts/ci.py prepare-blender --platform windows`.
3. Build exactly `${{ runner.temp }}/release/cats_blender_plugin-${RELEASE_VERSION}.zip`.
4. Validate source and ZIP with verified Blender and run
   `tests/verify_package.py` with verified Blender Python.
5. Run `prepare-release` to create `SHA256SUMS.txt` and outputs.
6. With `GH_TOKEN: ${{ github.token }}`, use `gh api`/`gh release view` to
   refuse an existing tag or release.
7. Create a draft with `gh release create "$TAG" --draft --generate-notes
   --title "$TAG" --target "${{ github.sha }}"`.
8. Upload the exact ZIP and `SHA256SUMS.txt`.
9. Download the stored ZIP into a new runner-temp directory.
10. Run `scripts/ci.py verify-file` using the pre-upload digest.
11. Publish with `gh release edit "$TAG" --draft=false`.

Do not add cleanup that deletes a failed draft.

- [ ] **Step 8: Run all helper and workflow policy tests**

```powershell
python -m unittest tests.test_ci -v
python scripts/ci.py check-release --version 5.2.1 --manifest blender_manifest.toml
python scripts/ci.py check-release --version 5.2.1-beta.1 --manifest blender_manifest.toml
git diff --check
```

Expected: unit tests pass; final `5.2.1` check exits 0; prerelease check exits nonzero with the `X.Y.Z` error; diff check passes.

- [ ] **Step 9: Commit manual verified release publication**

```powershell
git add -- scripts/ci.py tests/test_ci.py '.github/workflows/Cats Tests.yml'
git diff --cached --check
git commit -m "ci: publish verified final releases manually"
```

---

### Task 6: Remove dead CI-only files with preservation evidence

**Files:**
- Delete: `tests/termcolor.py`
- Delete: `tests/old/copy_protection.test.py`
- Delete: `tests/old/translate.test.py`
- Delete: `tests/old/viseme.test.py`

**Interfaces:**
- Consumes: active test discovery and workflow from Tasks 3-5.
- Produces: no replacement interface; deletes unreachable files only.

- [ ] **Step 1: Re-run the preservation search before deletion**

```powershell
rg -n "termcolor|cprint|colored|tests/old|copy_protection|translate\.test|viseme\.test" `
  .github scripts tests README.md docs `
  -g '*.py' -g '*.yml' -g '*.yaml' -g '*.md'
rg -n "cats_copyprotection" . -g '*.py'
```

Expected: no active importer or runner references `termcolor.py` or
`tests/old/`; `cats_copyprotection` appears only in the obsolete test.

- [ ] **Step 2: Delete only the confirmed dead files**

Use `apply_patch` to delete the four files. Do not alter active armature,
shape-key, smoke, or lifecycle tests.

- [ ] **Step 3: Run active unit/static preservation gates**

```powershell
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
git diff --check
```

Expected: all active tests and syntax checks pass.

- [ ] **Step 4: Commit dead-test cleanup separately**

```powershell
git add -- tests/termcolor.py tests/old/copy_protection.test.py `
  tests/old/translate.test.py tests/old/viseme.test.py
git diff --cached --check
git commit -m "test: remove unreachable legacy CI files"
```

---

### Task 7: Full local gate, GitHub matrix, review, and milestone handoff

**Files:**
- Modify: `docs/HANDOFF.md`
- Delete after all implementation checks pass: `docs/superpowers/specs/2026-08-08-ci-hardening-release-design.md`
- Delete after all implementation checks pass: `docs/superpowers/plans/2026-08-08-ci-hardening-release.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: review-ready branch with documented validation and no in-flight planning artifacts.

- [ ] **Step 1: Review complete branch scope and history**

```powershell
git log --oneline main..HEAD
git diff --stat main...HEAD
git diff --name-status main...HEAD
git status --short
```

Expected: only the approved CI helper, workflow, tests, dead-file deletion, and in-flight docs are present; the worktree is clean.

- [ ] **Step 2: Run the complete local static and helper gate**

```powershell
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --command extension validate .
git diff --check
```

Expected: all unit tests pass; syntax, source validation, and diff check exit 0.

- [ ] **Step 3: Build and verify the exact local package**

Because `scripts/build.py` refuses a dirty tracked tree, first commit any
intentional corrections from Step 2. Then run:

```powershell
python scripts/build.py --blend 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
```

Expected: source validation, package build, package validation, and
`tests/verify_package.py` pass. Record the final `.packaged-releases/` path;
do not stage the ZIP.

- [ ] **Step 4: Inspect the package member list and hash**

```powershell
$Package = Get-ChildItem '.packaged-releases' -Filter 'cats_blender_plugin-*.zip' `
  | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
python tests/verify_package.py $Package.FullName --source-dir .
Get-FileHash -Algorithm SHA256 $Package.FullName
```

Expected: verification passes; no `docs`, `scripts`, `tests`, local references,
runtime profiles, Git data, caches, or fixtures appear in the archive.

- [ ] **Step 5: Run correctness review before publication**

Invoke `superpowers:requesting-code-review` for the complete production diff.
If review feedback is received, invoke `superpowers:receiving-code-review`,
verify each claim, and return fixes through their own RED/GREEN cycle and
focused commit.

- [ ] **Step 6: Obtain publication authorization and run the GitHub matrix**

Stop and request explicit authorization before pushing or opening a pull
request. Once authorized, use the repository publication workflow to push
`codex/ci-hardening-release` and open a draft PR targeting `main`. Wait for the
`windows-2025`, `ubuntu-24.04`, and `macos-15` matrix entries and confirm every
preserved gate passes. Do not publish a GitHub release from the topic branch.

- [ ] **Step 7: Update the handoff with exact evidence**

Replace stale CI notes in `docs/HANDOFF.md` with:

- Branch objective and final commit.
- Three-platform runner coverage.
- Exact action and external-input pinning model.
- Local commands and results.
- Package path and SHA-256.
- PR/check results if publication was authorized.
- Known limitation: the real release path can only be exercised by manual
  final-version dispatch from public `main` after merge.
- Recommended next action: review/merge the PR, then use a future final-version
  dispatch when a release is intentionally being cut.

- [ ] **Step 8: Retire in-flight spec and plan as the milestone's last change**

After every implementation, review, local verification, and authorized GitHub
matrix check passes, use `apply_patch` to delete both in-flight documents. Git
history at `f72d4af` and the plan commit retains their rationale.

- [ ] **Step 9: Commit the final handoff and document retirement**

```powershell
git add -- docs/HANDOFF.md `
  docs/superpowers/specs/2026-08-08-ci-hardening-release-design.md `
  docs/superpowers/plans/2026-08-08-ci-hardening-release.md
git diff --cached --check
git commit -m "docs: hand off verified CI hardening"
```

- [ ] **Step 10: Run final verification-before-completion**

```powershell
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
git diff --check
git status --short
git log --oneline main..HEAD
```

Expected: tests and checks pass, worktree is clean, commits are coherently
scoped, and no ignored/generated material is staged or tracked.

The manual final-release dispatch is intentionally not part of branch
completion. It is performed only from public `main` for an intentionally
prepared final `X.Y.Z` release after merge.
