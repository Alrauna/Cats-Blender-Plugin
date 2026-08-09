# Handoff

## Repository state

- Base/default branch: `origin/main` at
  `90c1f194dedda1d5657a7b50ceff1a7dce4471cd` after a fresh fetch on
  2026-08-09.
- Completed topic branch: `codex/release-attestation-5-2-2`, based directly on
  that commit. Its production/workflow head is
  `c11acff3b521a81af43efae0961b666d59441da7`.
- GitHub currently has no open pull requests. The latest published release is
  still `v5.2.1`; no 5.2.2 tag, release, or workflow dispatch was created.
- The tracked worktree was clean before this handoff update. Generated Blender
  profiles and packages remain ignored under `.test-runtime/` and
  `.packaged-releases/`.
- The old handoff claims that version 5.2.1 remained checked in and that the
  implementation plan still awaited approval were stale. Manifest and runtime
  versions are now synchronized at final version `5.2.2`, and the approved
  implementation is complete.

## Completed changes

- `98420ae` — split the release workflow into credential-isolated jobs and add
  contract tests.
- `df47752` — synchronize `blender_manifest.toml` and `CATS_VERSION` at 5.2.2
  and document consumer attestation verification.
- `c11acff` — make the existing-tag/release preflight fail closed on GitHub API
  errors and add its regression contract.

The release graph is now:

1. `draft_release` depends on `validate` and `release_gate`, uses the `release`
   environment, and has only `contents: write`. It has no `uses:` steps. It
   fetches and verifies the exact public `main` commit, builds and validates the
   ZIP, creates a draft, uploads the ZIP and checksum, downloads the stored ZIP
   by numeric asset ID, verifies the GitHub digest metadata and bytes, and emits
   only tag, archive name, SHA-256, release ID, and asset ID.
2. `attest_release` depends on `draft_release`, has exactly `contents: read`,
   `id-token: write`, and `attestations: write`, and has no environment. It
   downloads the exact draft asset by numeric ID, independently checks draft
   identity, target commit, asset name/ID/digest, and bytes, then attests only
   that ZIP with
   `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`.
3. `publish_release` depends on both earlier jobs, uses the `release`
   environment, and has only `contents: write`. It has no `uses:` steps. It
   repeats the exact identity and byte checks before publishing that numeric
   draft release. An attestation failure therefore leaves the release as a
   draft.

No workflow artifact transfer was added. The stored draft-release asset is the
handoff between runners. Routine CI artifacts, checksums, source archives,
caches, and unrelated files are not attested.

Full-SHA pinning limits action-version substitution but does not solve the
problem of an action receiving a job's `github.token`; actions may access that
token even when it is not passed explicitly. The security control is the job
boundary: the attestation action never runs with `contents: write`, and both
write-token jobs contain only first-party shell commands.

The independent security review initially found that the inherited tag/release
existence probes treated every `gh` failure as absence. The accepted RED/GREEN
fix uses successful list queries under `set -euo pipefail`, exact-match `jq -e`
predicates, and pagination. Authentication, rate-limit, network, server, or
malformed-response failures now stop before draft creation. Re-review reported
no remaining Critical or Important findings.

## Local verification

The following passed on Windows with Blender 5.2 and isolated profiles:

- `python -m unittest tests.test_ci -v` — 24 tests.
- Explicit-path `compileall` over source and tests.
- `blender.exe --factory-startup --command extension validate .`.
- `python scripts/build.py --blend <Blender 5.2>`.
- Independent `tests/verify_package.py` verification.
- `git diff --check` and clean tracked status.

Verified package from production/workflow head `c11acff`:

- Path:
  `.packaged-releases/cats_blender_plugin-5.2.2-c11acff.zip`.
- SHA-256:
  `0db47b443ab9773e4a1eea3e8e180c653fe1bed0cd4c42345db26572e3b8479f`.
- Contents: 183 files and 129 Python modules; manifest is Blender 5.2
  compatible and versioned 5.2.2.
- Package verification excludes repository-only, local-reference, runtime,
  cache, and generated material. The ZIP remains ignored and must not be
  staged.

## Hosted-only checks and operational caveats

Local tests cannot prove GitHub-hosted behavior for:

- YAML parsing and execution on the Windows 2025 and Ubuntu 24.04 runners.
- A read-only `GITHUB_TOKEN` downloading the unpublished draft asset by numeric
  asset ID.
- OIDC issuance, Sigstore/GitHub attestation persistence, and later
  `gh attestation verify` behavior.
- GitHub release API digest population and identity checks in the live run.
- The failed-attestation path leaving the release draft, followed by successful
  exact-release publication.
- Environment approval UX. The `release` environment was re-queried on
  2026-08-09 and still has `protection_rules: []` and no deployment branch
  policy. It prompts for no approval today. If reviewers are enabled later,
  the two write jobs may require two sequential approvals; this is an
  intentional cost of isolating the attestation action from write credentials.

CATS intentionally differs from AMS by binding and rechecking numeric release
and asset IDs plus GitHub's stored digest, because CATS creates and publishes a
draft release in one workflow and does not need a second artifact-transfer
channel. It also keeps its own version policy and uses 5.2.2, not AMS 1.3.1.

## Next action

Request explicit authorization to push this branch and open a draft pull
request targeting `main`. Then require the three-platform validation matrix,
CodeQL, and review of the hosted workflow syntax/results. Do not dispatch
`release=5.2.2` during PR validation or merge. After review and merge, an
authorized maintainer can intentionally dispatch 5.2.2 from public `main` and
manually verify the draft, attestation, and publication behavior.
