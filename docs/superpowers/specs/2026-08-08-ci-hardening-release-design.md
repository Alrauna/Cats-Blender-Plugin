# CI Hardening and Manual Release Design

## Goal

Harden every external input used by CATS CI, run the existing extension gates
on Windows, Linux, and macOS Apple Silicon, remove dead CI baggage, and add a
manual final-release path that publishes only a freshly built and verified
universal package with its SHA-256 checksum.

This design follows the security model used by
`Alrauna/material-combiner-addon` and
`Alrauna/blender-alpha-material-separator`, including their independent
resolver consensus for Blender checksums. It preserves CATS-specific package,
installation, runtime, and removal tests instead of replacing them with the
companions' project-specific suites.

## Scope

The change will:

- Retain `.github/workflows/Cats Tests.yml` as the single validation and
  release workflow.
- Add `scripts/ci.py` as the sole new implementation module.
- Validate on `windows-2025`, `ubuntu-24.04`, and `macos-15` Apple Silicon.
- Pin every GitHub Action by a full commit SHA and disable checkout credential
  persistence.
- Pin and verify Blender 5.2.0 archives and all three remotely retained CATS
  test assets before execution.
- Preserve the existing source validation, package validation, package-content
  verification, isolated installation, background smoke suites, armature and
  shape-key suites, lifecycle cleanup, removal, and absence checks.
- Add manual final release publication for exact `X.Y.Z` versions.
- Delete `tests/termcolor.py` and `tests/old/` after preservation checks.
- Replace the workflow's `compileall .` with the explicit paths required by
  `AGENTS.md`.

The change will not add scheduled runs, prerelease publication, automatic
publication, a release dry run, dependency or package caching, lint
dependencies, reusable workflows, split-platform packages, or another workflow
file.

## Repository and branch boundaries

The work is one topic branch whose sole objective is CI input hardening,
three-platform validation, dead CI cleanup, and manual final-release
publication. Product features, runtime archive import, live translations, and
the disabled in-product updater are outside this branch.

The implementation must preserve the flat extension-package root and keep all
CI helpers, tests, and documentation excluded from the built package through
`blender_manifest.toml` and `tests/verify_package.py`.

## CI architecture

### Single workflow

`.github/workflows/Cats Tests.yml` remains the only workflow. It responds to:

- Pull requests targeting `main`.
- Pushes to `main`.
- Manual dispatch.

There is no `schedule` trigger. The obsolete `dev`, `forked_dev`, and
`blender-52` push and pull-request branches are removed.

Workflow-level permissions remain `contents: read`. Concurrency cancellation
applies only to superseded pull-request runs; pushes and manual dispatches are
never cancelled automatically because interruption during release publication
could leave partial external state.

### Validation matrix

The validation job uses a fail-independent matrix:

| Runner | Platform key | Blender archive |
| --- | --- | --- |
| `windows-2025` | `windows` | `blender-5.2.0-windows-x64.zip` |
| `ubuntu-24.04` | `linux` | `blender-5.2.0-linux-x64.tar.xz` |
| `macos-15` | `macos` | `blender-5.2.0-macos-arm64.dmg` |

Each entry securely acquires Blender, uses Blender's bundled Python for syntax
and test orchestration, builds one universal CATS ZIP in runner temporary
storage, installs that ZIP into an isolated profile, runs every applicable
existing CATS gate, removes it, verifies absence, and uploads the tested ZIP
under a platform-qualified artifact name.

The workflow removes `actions/setup-python`; no host Python version is part of
the tested extension contract. The runner's preinstalled Python is used only to
bootstrap the standard-library-only `scripts/ci.py` until the verified Blender
Python path is available.

### Explicit syntax paths

Syntax checking uses Blender's verified Python with exactly these source paths:

```text
__init__.py globs.py extentions.py updater.py tools ui extern_tools tests
```

It does not pass `.` to `compileall`, so local CI reproduction cannot descend
into `.local-references/` or `.test-runtime/` and write bytecode there.

## Verified Blender acquisition

`scripts/ci.py prepare-blender` adapts the companion repositories' maximum
hardening implementation.

For the selected platform it will:

1. Fetch Blender's official `blender-5.2.0.sha256` manifest through the
   runner's resolver.
2. Fetch the same manifest through Cloudflare DNS-over-HTTPS.
3. Resolve `download.blender.org` independently through Quad9 DNS-over-TLS and
   fetch the manifest using the returned addresses with the original TLS host.
4. Require all three manifest payloads to be byte-identical.
5. Parse the manifest strictly and require its selected digest to match the
   platform digest committed in `scripts/ci.py`.
6. Download the archive over HTTPS with bounded connection, total, retry, and
   process timeouts.
7. Require the downloaded archive's SHA-256 to match the committed digest.
8. Extract only after verification.
9. Locate Blender and its bundled Python and require the reported version to
   equal `Blender 5.2.0 LTS`.

The committed Blender digests are:

| Platform | SHA-256 |
| --- | --- |
| Windows x64 | `2d184b626c001692c362291911293b6a297179d618d95e9e9192c3a80318adc4` |
| Linux x64 | `96f6c181a30f4950607839dc84d42a354b250d8a0231b098b59b7bc69c351c48` |
| macOS ARM64 | `ed4d8390166dec5ea0a2813a03db6221f206ce016442be7f59f41d760972568a` |

Linux extraction uses the standard-library data filter to reject absolute
paths, parent traversal, and escaping links. Windows uses standard ZIP
extraction after digest verification. macOS attaches the verified DMG read-only
with `hdiutil`, parses its plist output, copies the single Blender application
bundle while preserving internal symlinks, and detaches the image in `finally`.

The independent DNS implementation is an explicitly approved exception to the
usual minimal-code preference. It adds no third-party dependency and receives
targeted parser and consensus tests.

## Verified test assets

`tests/run.py` extends `TestAsset` with a required SHA-256 digest. The committed
digests, computed from the maintainer's canonical ignored copies, are:

| Asset | SHA-256 |
| --- | --- |
| `armatures/armature.ryuko.blend` | `d92b918968e7d0f2d06ef75ba739b85091fc5409954d2dcd880aed21af09a6db` |
| `armatures/armature.bonetranslationerror.blend` | `1b4c3e2cd02a5bd611c44aa8261f6a45c07f67cbb81d7e09cbe3ff85dc788014` |
| `shapekeys/shapekey.shape_key_to_basis.blend` | `a596211cfcd3c6bdd7b1b78218de2940b9c9b8f96b756374a9a1a55b73df8223` |

Both existing and newly downloaded files are checked before use. Downloads are
streamed to the existing `.part` path through a 256 MiB maximum. The runner
requires the exact digest and existing Blender-magic check before atomically
replacing the destination. Any failure removes the partial download and stops
the test run; there is no unverified fallback.

Background Blender fixture runs explicitly use `--disable-autoexec` in addition
to their existing `--offline-mode` and isolated profile.

## Manual final release

Manual dispatch keeps an optional `release` string. An empty value runs
validation only. A non-empty value can reach release jobs only when:

- The event is `workflow_dispatch`.
- The ref is `refs/heads/main`.
- The repository is public.
- The value matches final-version syntax `X.Y.Z` with no suffix.
- The value exactly matches `blender_manifest.toml`.
- The three-platform validation matrix and the fast release-input gate pass.

The release job alone receives `contents: write` and uses a protected `release`
environment. It will:

1. Initialize an empty workspace and fetch the exact public `${{ github.sha }}`
   without credentials.
2. Verify the checked-out commit equals `${{ github.sha }}`.
3. Acquire the pinned Windows Blender through the same hardened helper.
4. Build a fresh universal `cats_blender_plugin-X.Y.Z.zip` into
   `${{ runner.temp }}`.
5. Validate the source and ZIP with Blender and run
   `tests/verify_package.py` against the fresh ZIP.
6. Derive tag `vX.Y.Z` from the manifest-controlled version.
7. Write `SHA256SUMS.txt` for the ZIP.
8. Refuse to overwrite an existing tag or release.
9. Create a draft release targeting the exact source SHA.
10. Upload the ZIP and checksum file.
11. Download the stored ZIP and verify it against the pre-upload digest.
12. Publish the draft only after stored-asset verification succeeds.

A failure leaves a recoverable draft. The workflow does not delete, overwrite,
or reuse an existing tag or release.

## Helper interfaces

`scripts/ci.py` exposes four command-line commands:

- `prepare-blender --platform {windows,linux,macos} --output-dir PATH
  --github-output PATH`
- `check-release --version X.Y.Z --manifest blender_manifest.toml`
- `prepare-release --version X.Y.Z --manifest blender_manifest.toml
  --archive PATH --checksum-output PATH --github-output PATH`
- `verify-file --file PATH --expected-sha256 DIGEST`

Every GitHub output is a single line; carriage returns and line feeds are
rejected before writing. All version, digest, archive-name, and manifest values
are validated before use.

## Failure behavior

The pipeline fails closed on resolver disagreement, malformed DNS or checksum
data, official-versus-committed checksum drift, archive or fixture digest
mismatch, unsafe extraction, unexpected Blender version, malformed release
input, manifest mismatch, GitHub-output injection, package validation failure,
existing release identity, or stored-asset mismatch.

Temporary download files are deleted on failure. A mounted macOS disk image is
detached in `finally`. No security failure is downgraded to a warning.

## Test strategy

Implementation uses test-driven development. `tests/test_ci.py` uses only
`unittest` and the standard library and covers:

- Strict checksum-manifest parsing, including malformed and duplicate rows.
- Independent DNS response decoding limits and malformed responses.
- Three-resolver checksum consensus and disagreement.
- Official-versus-committed digest agreement.
- File hashing and digest validation.
- Final `X.Y.Z` acceptance and prerelease rejection.
- Requested-versus-manifest version mismatch.
- Release tag, archive-name, and checksum output.
- GitHub-output carriage-return and newline rejection.
- Fixture success, corruption, oversize, partial-file cleanup, and existing-file
  verification.
- Workflow policy requiring full-SHA action pins, non-persisted checkout
  credentials, and global read-only permissions.

The matrix itself is the integration test for three-platform downloads,
extraction, executable discovery, Blender version reporting, package creation,
isolated installation, runtime behavior, and removal.

Before completion, run locally applicable unit and static checks, then exercise
the full workflow on the topic pull request. The release path is accepted only
after a manual final-version dispatch on `main`; it is not simulated by an
alternate dry-run implementation.

## Dead CI cleanup

`tests/termcolor.py` is deleted because no runner or test imports it.

The three files under `tests/old/` are deleted only after confirming:

- They are absent from every active runner and workflow.
- `copy_protection.test.py` targets an operator no longer present.
- The translation and viseme files are nondeterministic legacy button probes,
  not assertions of a stable output contract.
- No current supported behavior loses active coverage because of their
  deletion.

The cleanup is isolated in its own commit after the security and validation
gates are green.

## Acceptance criteria

- Pull requests and pushes to `main` run the full Windows, Linux, and macOS ARM
  matrix; no scheduled workflow exists.
- Every action and externally downloaded test/executable input is immutably
  pinned and verified before execution.
- All existing CATS validation and lifecycle gates pass on all three platforms.
- The tested package artifacts remain universal packages and contain no
  repository-only, local-only, generated, or test material.
- Manual dispatch with an empty release value performs validation only.
- Manual dispatch with a mismatched, prerelease, non-main, private-repository,
  existing, or invalid release request cannot publish.
- A valid manual final release rebuilds from the exact public commit, uploads a
  ZIP and `SHA256SUMS.txt`, verifies the stored ZIP, and only then publishes.
- No automatic, scheduled, or prerelease publication path exists.
- `git diff --check` passes and the final branch contains no ignored runtime,
  reference, profile, fixture, cache, or package output.
