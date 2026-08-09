# Release Attestation and Version 5.2.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Parallel or
> subagent execution requires separate explicit user approval.

**Goal:** Prepare CATS 5.2.2 and make its primary release ZIP publication
depend on a signed GitHub provenance attestation created in a read-only job.

**Architecture:** Split the existing monolithic release job into an
action-free draft job with `contents: write`, a read-only attestation job with
OIDC and attestation permissions, and an action-free publication job with
`contents: write`. Pass only validated identity/digest strings between jobs;
download the exact draft asset by numeric ID and verify it independently in
every downstream job.

**Tech Stack:** GitHub Actions YAML, hosted `bash`/GitHub CLI/`jq`, Python 3
`unittest`, Blender 5.2 extension tooling, `actions/attest` v4.2.2 pinned to
`1e69f48acb82d1966a394da916b4c1698aa569d6`.

## Global Constraints

- Target Blender 5.2 LTS; keep `blender_version_min = "5.2.0"`.
- Set both manifest version and `CATS_VERSION` to exact final `5.2.2`.
- Keep global workflow permissions at `contents: read`.
- No job containing a `uses:` step may have `contents: write`.
- Only `attest_release` may have `id-token: write` or `attestations: write`.
- Attest only the primary CATS extension ZIP stored on the draft release.
- Preserve manual, non-empty-version, public-`main`, validation, and release
  gate conditions.
- Preserve exact public-source rebuilding and all current validation gates.
- Introduce no dependency, workflow-artifact transfer, SBOM, custom predicate,
  cache, source-archive attestation, or automatic release.
- Do not tag, dispatch, publish, push, or open a pull request without the
  separately required authorization.
- Use the existing `release` environment on both write-capable jobs. Do not
  claim it has protection rules; it currently has none.

## File Structure

- `.github/workflows/Cats Tests.yml`: release job graph, permissions, identity
  outputs, draft-asset verification, attestation, and publication.
- `tests/test_ci.py`: workflow job-block helpers and security/data-flow
  contracts.
- `blender_manifest.toml`: authoritative version `5.2.2`.
- `__init__.py`: synchronized `CATS_VERSION = "5.2.2"`.
- `README.md`: consumer provenance verification command.
- `docs/HANDOFF.md`: exact branch state, validation evidence, limitations, and
  next action.
- `docs/superpowers/specs/2026-08-08-release-attestation-5-2-2-design.md` and
  this plan: delete only after the milestone is implemented, reviewed, and
  verified.

---

### Task 1: Add RED workflow security contracts

**Files:**
- Modify: `tests/test_ci.py`
- Test: `tests/test_ci.py`

**Interfaces:**
- Consumes: `.github/workflows/Cats Tests.yml` as UTF-8 text.
- Produces: `workflow_job(workflow: str, name: str) -> str` and
  `job_permissions(block: str) -> set[str]` test helpers; contracts for
  `draft_release`, `attest_release`, and `publish_release`.

- [ ] **Step 1: Add focused test-only workflow parsers**

Add `import re` at module scope and these helpers below `load_ci_module`:

```python
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
```

Move the existing local `import re` out of
`test_actions_are_immutable_and_checkout_drops_credentials`; reuse the module
import.

- [ ] **Step 2: Add the credential-isolation RED test**

Add to `WorkflowPolicyTests`:

```python
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
```

- [ ] **Step 3: Add the data-flow and fail-closed RED test**

Add to `WorkflowPolicyTests`:

```python
def test_release_jobs_bind_and_reverify_the_stored_primary_zip(self):
    draft = workflow_job(self.workflow, "draft_release")
    attest = workflow_job(self.workflow, "attest_release")
    publish = workflow_job(self.workflow, "publish_release")

    self.assertIn("needs: [validate, release_gate]", draft)
    self.assertIn("needs: draft_release", attest)
    self.assertIn("needs: [draft_release, attest_release]", publish)
    outputs = re.search(
        r"^    outputs:\n(?P<body>(?:^      [a-z_]+: .+\n)+)",
        draft,
        re.MULTILINE,
    )
    self.assertIsNotNone(outputs)
    output_names = set(
        re.findall(r"^      ([a-z_]+):", outputs.group("body"), re.MULTILINE)
    )
    self.assertEqual(
        {"tag", "archive_name", "sha256", "release_id", "asset_id"},
        output_names,
    )
    for output in ("tag", "archive_name", "sha256", "release_id", "asset_id"):
        self.assertIn(f"      {output}: ${{{{ steps.", draft)
        self.assertIn(f"needs.draft_release.outputs.{output}", attest)
        self.assertIn(f"needs.draft_release.outputs.{output}", publish)
    self.assertIn("releases/assets/${ASSET_ID}", attest)
    self.assertIn("releases/assets/${ASSET_ID}", publish)
    self.assertIn("sha256sum", attest)
    self.assertIn("sha256sum", publish)
    self.assertIn(
        "subject-path: '${{ runner.temp }}/stored-release/"
        "${{ needs.draft_release.outputs.archive_name }}'",
        attest,
    )
    self.assertEqual(1, attest.count("subject-path:"))
    self.assertNotIn("subject-checksums:", attest)
    self.assertIn("releases/${RELEASE_ID}", publish)
    self.assertIn("-F draft=false", publish)
    self.assertNotIn("actions/upload-artifact", draft + attest + publish)
    self.assertNotIn("actions/download-artifact", draft + attest + publish)
```

Replace the old `test_release_is_manual_main_only_and_write_scoped` with:

```python
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
    self.assertIn('test "$(git rev-parse HEAD)" = "${EXPECTED_SHA}"', draft)
    self.assertIn("SHA256SUMS.txt", draft)
    self.assertIn("--draft", draft)
```

- [ ] **Step 4: Run the new tests and verify RED**

Run:

```powershell
python -m unittest `
  tests.test_ci.WorkflowPolicyTests.test_release_jobs_isolate_write_tokens_from_actions `
  tests.test_ci.WorkflowPolicyTests.test_release_jobs_bind_and_reverify_the_stored_primary_zip `
  -v
```

Expected: both tests fail because `draft_release`, `attest_release`, and
`publish_release` do not exist. Existing tests may also fail only where they
still encode the old monolithic job and must be revised as described above;
do not weaken unrelated policies.

---

### Task 2: Split the release pipeline and make attestation a publication gate

**Files:**
- Modify: `.github/workflows/Cats Tests.yml`
- Test: `tests/test_ci.py`

**Interfaces:**
- Consumes: `validate`, `release_gate`, `scripts/ci.py prepare-release`, the
  public `${{ github.sha }}`, and GitHub release/asset REST APIs.
- Produces: `draft_release.outputs.{tag,archive_name,sha256,release_id,asset_id}`;
  signed provenance for the stored primary ZIP; publication only after
  successful attestation.

- [ ] **Step 1: Rename the current release job and expose validated outputs**

Rename `release` to `draft_release`, keep its existing condition, Windows
runner, timeout, `release` environment, `contents: write`, exact-source fetch,
Blender acquisition, build/validation, release identity, existing-release
refusal, draft creation, and asset upload.

Add these job outputs:

```yaml
outputs:
  tag: ${{ steps.release_meta.outputs.tag }}
  archive_name: ${{ steps.release_meta.outputs.archive_name }}
  sha256: ${{ steps.release_meta.outputs.sha256 }}
  release_id: ${{ steps.stored_release.outputs.release_id }}
  asset_id: ${{ steps.stored_release.outputs.asset_id }}
```

Rename the current stored-ZIP step to `Verify stored draft release`, give it
`id: stored_release`, and remove the final publication step from this job.

- [ ] **Step 2: Make the draft verification emit exact release/asset IDs**

Use this logic in `Verify stored draft release`, retaining environment-based
inputs so no GitHub context or job output is interpolated directly into shell
source:

```yaml
- name: Verify stored draft release
  id: stored_release
  env:
    GH_TOKEN: ${{ github.token }}
    TAG: ${{ steps.release_meta.outputs.tag }}
    ARCHIVE_NAME: ${{ steps.release_meta.outputs.archive_name }}
    EXPECTED_SHA256: ${{ steps.release_meta.outputs.sha256 }}
  run: |
    set -euo pipefail
    releases_json="$(gh api "repos/${GITHUB_REPOSITORY}/releases?per_page=100" --paginate --slurp)"
    release_id="$(printf '%s' "${releases_json}" | jq -er --arg tag "${TAG}" '[.[][] | select(.draft == true and .tag_name == $tag)] | if length == 1 then .[0].id else error("draft release is missing or duplicated") end')"
    release_json="$(gh api "repos/${GITHUB_REPOSITORY}/releases/${release_id}")"
    asset_id="$(printf '%s' "${release_json}" | jq -er --arg name "${ARCHIVE_NAME}" '[.assets[] | select(.name == $name)] | if length == 1 then .[0].id else error("primary release asset is missing or duplicated") end')"
    [[ "${release_id}" =~ ^[0-9]+$ ]]
    [[ "${asset_id}" =~ ^[0-9]+$ ]]
    stored_dir='${{ runner.temp }}/stored-release'
    mkdir -p "${stored_dir}"
    gh api -H 'Accept: application/octet-stream' \
      "repos/${GITHUB_REPOSITORY}/releases/assets/${asset_id}" \
      > "${stored_dir}/${ARCHIVE_NAME}"
    python scripts/ci.py verify-file \
      --file "${stored_dir}/${ARCHIVE_NAME}" \
      --expected-sha256 "${EXPECTED_SHA256}"
    echo "release_id=${release_id}" >> "${GITHUB_OUTPUT}"
    echo "asset_id=${asset_id}" >> "${GITHUB_OUTPUT}"
```

- [ ] **Step 3: Add a shared action-free identity/digest check to both downstream jobs**

In both downstream jobs, pass outputs through environment variables:

```yaml
env:
  GH_TOKEN: ${{ github.token }}
  TAG: ${{ needs.draft_release.outputs.tag }}
  ARCHIVE_NAME: ${{ needs.draft_release.outputs.archive_name }}
  EXPECTED_SHA256: ${{ needs.draft_release.outputs.sha256 }}
  RELEASE_ID: ${{ needs.draft_release.outputs.release_id }}
  ASSET_ID: ${{ needs.draft_release.outputs.asset_id }}
```

Use this shell body before attestation and again immediately before
publication:

```bash
set -euo pipefail
[[ "${RELEASE_ID}" =~ ^[0-9]+$ ]]
[[ "${ASSET_ID}" =~ ^[0-9]+$ ]]
[[ "${EXPECTED_SHA256}" =~ ^[0-9a-f]{64}$ ]]
release_json="$(gh api "repos/${GITHUB_REPOSITORY}/releases/${RELEASE_ID}")"
printf '%s' "${release_json}" | jq -e \
  --arg tag "${TAG}" \
  --arg name "${ARCHIVE_NAME}" \
  --argjson asset_id "${ASSET_ID}" \
  '.draft == true and .tag_name == $tag and
   ([.assets[] | select(.id == $asset_id and .name == $name)] | length == 1)' \
  >/dev/null
stored_dir='${{ runner.temp }}/stored-release'
mkdir -p "${stored_dir}"
stored_path="${stored_dir}/${ARCHIVE_NAME}"
gh api -H 'Accept: application/octet-stream' \
  "repos/${GITHUB_REPOSITORY}/releases/assets/${ASSET_ID}" \
  > "${stored_path}"
actual_sha256="$(sha256sum "${stored_path}")"
actual_sha256="${actual_sha256%% *}"
test "${actual_sha256}" = "${EXPECTED_SHA256}"
```

The two jobs intentionally duplicate this small trust-boundary check so neither
depends on filesystem state or implicit verification performed by another
runner.

- [ ] **Step 4: Add the read-only attestation job**

Add this job after `draft_release`:

```yaml
attest_release:
  name: Attest verified release artifact
  if: >-
    github.event_name == 'workflow_dispatch' &&
    inputs.release != '' &&
    github.ref == 'refs/heads/main' &&
    github.event.repository.visibility == 'public'
  needs: draft_release
  runs-on: ubuntu-24.04
  timeout-minutes: 10
  permissions:
    contents: read
    id-token: write
    attestations: write
  defaults:
    run:
      shell: bash
  steps:
    - name: Download and verify exact draft asset
      env:
        GH_TOKEN: ${{ github.token }}
        TAG: ${{ needs.draft_release.outputs.tag }}
        ARCHIVE_NAME: ${{ needs.draft_release.outputs.archive_name }}
        EXPECTED_SHA256: ${{ needs.draft_release.outputs.sha256 }}
        RELEASE_ID: ${{ needs.draft_release.outputs.release_id }}
        ASSET_ID: ${{ needs.draft_release.outputs.asset_id }}
      run: |
        set -euo pipefail
        [[ "${RELEASE_ID}" =~ ^[0-9]+$ ]]
        [[ "${ASSET_ID}" =~ ^[0-9]+$ ]]
        [[ "${EXPECTED_SHA256}" =~ ^[0-9a-f]{64}$ ]]
        release_json="$(gh api "repos/${GITHUB_REPOSITORY}/releases/${RELEASE_ID}")"
        printf '%s' "${release_json}" | jq -e \
          --arg tag "${TAG}" \
          --arg name "${ARCHIVE_NAME}" \
          --argjson asset_id "${ASSET_ID}" \
          '.draft == true and .tag_name == $tag and
           ([.assets[] | select(.id == $asset_id and .name == $name)] | length == 1)' \
          >/dev/null
        stored_dir='${{ runner.temp }}/stored-release'
        mkdir -p "${stored_dir}"
        stored_path="${stored_dir}/${ARCHIVE_NAME}"
        gh api -H 'Accept: application/octet-stream' \
          "repos/${GITHUB_REPOSITORY}/releases/assets/${ASSET_ID}" \
          > "${stored_path}"
        actual_sha256="$(sha256sum "${stored_path}")"
        actual_sha256="${actual_sha256%% *}"
        test "${actual_sha256}" = "${EXPECTED_SHA256}"

    - name: Attest stored release ZIP
      uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6
      with:
        subject-path: '${{ runner.temp }}/stored-release/${{ needs.draft_release.outputs.archive_name }}'
```

- [ ] **Step 5: Add the action-free publication job**

Add this job after `attest_release`:

```yaml
publish_release:
  name: Publish attested final release
  if: >-
    github.event_name == 'workflow_dispatch' &&
    inputs.release != '' &&
    github.ref == 'refs/heads/main' &&
    github.event.repository.visibility == 'public'
  needs: [draft_release, attest_release]
  runs-on: ubuntu-24.04
  timeout-minutes: 10
  environment: release
  permissions:
    contents: write
  defaults:
    run:
      shell: bash
  steps:
    - name: Reverify and publish exact draft release
      env:
        GH_TOKEN: ${{ github.token }}
        TAG: ${{ needs.draft_release.outputs.tag }}
        ARCHIVE_NAME: ${{ needs.draft_release.outputs.archive_name }}
        EXPECTED_SHA256: ${{ needs.draft_release.outputs.sha256 }}
        RELEASE_ID: ${{ needs.draft_release.outputs.release_id }}
        ASSET_ID: ${{ needs.draft_release.outputs.asset_id }}
      run: |
        set -euo pipefail
        [[ "${RELEASE_ID}" =~ ^[0-9]+$ ]]
        [[ "${ASSET_ID}" =~ ^[0-9]+$ ]]
        [[ "${EXPECTED_SHA256}" =~ ^[0-9a-f]{64}$ ]]
        release_json="$(gh api "repos/${GITHUB_REPOSITORY}/releases/${RELEASE_ID}")"
        printf '%s' "${release_json}" | jq -e \
          --arg tag "${TAG}" \
          --arg name "${ARCHIVE_NAME}" \
          --argjson asset_id "${ASSET_ID}" \
          '.draft == true and .tag_name == $tag and
           ([.assets[] | select(.id == $asset_id and .name == $name)] | length == 1)' \
          >/dev/null
        stored_dir='${{ runner.temp }}/stored-release'
        mkdir -p "${stored_dir}"
        stored_path="${stored_dir}/${ARCHIVE_NAME}"
        gh api -H 'Accept: application/octet-stream' \
          "repos/${GITHUB_REPOSITORY}/releases/assets/${ASSET_ID}" \
          > "${stored_path}"
        actual_sha256="$(sha256sum "${stored_path}")"
        actual_sha256="${actual_sha256%% *}"
        test "${actual_sha256}" = "${EXPECTED_SHA256}"
        gh api --method PATCH \
          "repos/${GITHUB_REPOSITORY}/releases/${RELEASE_ID}" \
          -F draft=false --silent
```

Do not use `actions/checkout`, `actions/download-artifact`, or any other action
in either write-capable job.

- [ ] **Step 6: Run targeted and complete CI policy tests to verify GREEN**

Run:

```powershell
python -m unittest `
  tests.test_ci.WorkflowPolicyTests.test_release_jobs_isolate_write_tokens_from_actions `
  tests.test_ci.WorkflowPolicyTests.test_release_jobs_bind_and_reverify_the_stored_primary_zip `
  -v
python -m unittest tests.test_ci -v
git diff --check
```

Expected: all workflow-policy and CI helper tests pass. Review every `uses:`
reference and confirm the existing immutable-SHA test still sees only 40-digit
commit references.

- [ ] **Step 7: Commit the isolated release-attestation pipeline**

```powershell
git add -- tests/test_ci.py '.github/workflows/Cats Tests.yml'
git diff --cached --check
git diff --cached
git commit -m "ci: isolate release attestation credentials"
```

---

### Task 3: Increment CATS to 5.2.2 and document verification

**Files:**
- Modify: `blender_manifest.toml`
- Modify: `__init__.py`
- Modify: `README.md`
- Test: `tests/test_ci.py`, `tests/verify_package.py`

**Interfaces:**
- Consumes: manifest version source of truth and imported `CATS_VERSION`.
- Produces: exact final `5.2.2` identity and consumer verification guidance.

- [ ] **Step 1: Demonstrate the version gate RED**

Run before editing versions:

```powershell
python scripts/ci.py check-release --version 5.2.2 --manifest blender_manifest.toml
```

Expected: nonzero exit with `manifest version '5.2.1' does not match '5.2.2'`.

- [ ] **Step 2: Apply the minimal synchronized version edit**

Change exactly:

```toml
# blender_manifest.toml
version = "5.2.2"
```

```python
# __init__.py
CATS_VERSION = "5.2.2"
```

Do not change `blender_version_min`, updater URLs, compatibility metadata, or
introduce another version definition.

- [ ] **Step 3: Add consumer provenance verification documentation**

After the installation warning in `README.md`, add:

````markdown
### Verify release provenance

GitHub releases from version 5.2.2 onward include signed build provenance for
the CATS extension ZIP. After downloading the ZIP, verify it online with
GitHub CLI:

```text
gh attestation verify cats_blender_plugin-5.2.2.zip \
  -R Alrauna/Cats-Blender-Plugin
```

`SHA256SUMS.txt` verifies file integrity; the attestation additionally verifies
the repository and GitHub Actions workflow that produced the ZIP.
````

- [ ] **Step 4: Verify the version gate GREEN and static contracts**

Run:

```powershell
python scripts/ci.py check-release --version 5.2.2 --manifest blender_manifest.toml
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
git diff --check
```

Expected: release check, all CI tests, syntax compilation, and diff check pass.

- [ ] **Step 5: Commit the synchronized 5.2.2 release identity**

```powershell
git add -- blender_manifest.toml __init__.py README.md
git diff --cached --check
git diff --cached
git commit -m "release: prepare CATS 5.2.2"
```

---

### Task 4: Review and run the complete local release gate

**Files:**
- Inspect: all branch changes
- Generated and ignored: `.packaged-releases/cats_blender_plugin-5.2.2-*.zip`
- Generated and ignored: `.test-runtime/`

**Interfaces:**
- Consumes: committed workflow, tests, version metadata, and documentation.
- Produces: review findings, exact validation results, package path/member
  count/SHA-256, and confirmed clean tracked state.

- [ ] **Step 1: Review complete branch scope and credential boundaries**

Run:

```powershell
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
git diff --name-status origin/main...HEAD
git diff origin/main...HEAD -- '.github/workflows/Cats Tests.yml' tests/test_ci.py
git status --short
```

Manually verify:

- Every job's exact permissions and environment.
- Every `uses:` step is full-SHA pinned and absent from write jobs.
- All untrusted or cross-job values reach shell through `env`.
- IDs/digest are validated before use.
- Both downstream jobs verify the exact release/asset identity and bytes.
- Attestation failure blocks publication.
- No branch/tag/release operation occurs outside the authorized manual path.

- [ ] **Step 2: Invoke correctness/security review**

Use `superpowers:requesting-code-review` for the full material workflow diff.
Because multi-agent execution is not authorized, perform the review inline or
through an available non-subagent review mechanism. If feedback is received,
use `superpowers:receiving-code-review`, verify each finding, and fix accepted
issues through their own focused RED/GREEN cycle and commit.

- [ ] **Step 3: Run static, helper, and Blender source validation**

Run:

```powershell
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --command extension validate .
git diff --check
git status --short
```

Expected: every command passes and the tracked tree is clean. Generated ignored
runtime state may exist only under `.test-runtime/` or `.packaged-releases/`.

- [ ] **Step 4: Build and verify the committed 5.2.2 package**

Run from the clean commit:

```powershell
python scripts/build.py --blend 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Package = Get-ChildItem '.packaged-releases' -Filter 'cats_blender_plugin-5.2.2-*.zip' |
  Sort-Object LastWriteTimeUtc -Descending |
  Select-Object -First 1
python tests/verify_package.py $Package.FullName --source-dir .
Get-FileHash -Algorithm SHA256 $Package.FullName
```

Expected: source/package validation and package verification pass. Record the
exact ignored package path, SHA-256, member count, Python module count, and
absence of repository-only/local/runtime/cache content. Do not stage the ZIP.

---

### Task 5: Final handoff, document retirement, and branch verification

**Files:**
- Modify: `docs/HANDOFF.md`
- Delete: `docs/superpowers/specs/2026-08-08-release-attestation-5-2-2-design.md`
- Delete: `docs/superpowers/plans/2026-08-09-release-attestation-5-2-2.md`

**Interfaces:**
- Consumes: complete committed implementation and exact review/validation
  evidence.
- Produces: review-ready branch with a durable handoff and no superseded
  in-flight documents.

- [ ] **Step 1: Update the handoff with exact completed evidence**

Record:

- Branch purpose and final implementation commits.
- Exact three-job permission and dependency model.
- Why full-SHA pinning is necessary but job isolation is the credential control.
- Current `release` environment state: no protection rules or branch policy.
- Local commands/results and exact package path/SHA-256/member inspection.
- Hosted-only limitations: draft asset download with a read-only job token,
  OIDC/Sigstore/API persistence, environment approval behavior, failure draft,
  and final publication.
- The explicit instruction not to dispatch or publish 5.2.2 during branch
  completion.
- Recommended next action: authorize push/draft PR for GitHub parsing and the
  three-platform matrix, then review/merge; only later intentionally dispatch
  5.2.2 from public `main`.

- [ ] **Step 2: Retire the in-flight design and plan**

After all implementation, review, and local verification passes, delete the
two files listed above with `apply_patch`. Git history retains both documents.

- [ ] **Step 3: Commit the milestone handoff**

```powershell
git add -- docs/HANDOFF.md `
  docs/superpowers/specs/2026-08-08-release-attestation-5-2-2-design.md `
  docs/superpowers/plans/2026-08-09-release-attestation-5-2-2.md
git diff --cached --check
git diff --cached
git commit -m "docs: hand off attested 5.2.2 release"
```

- [ ] **Step 4: Run verification-before-completion against the final commit**

Run:

```powershell
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --command extension validate .
python scripts/build.py --blend 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
git diff --check
git status --short
git log --oneline origin/main..HEAD
```

Expected: all checks and the final exact-commit build pass; the worktree is
clean; branch history contains only the design revision, plan, workflow/test,
version/docs, and final handoff units.

- [ ] **Step 5: Stop for publication authorization**

Do not push or create a pull request automatically. Report the local branch as
ready and request authorization. If authorized later, push this branch, open a
draft PR targeting `main`, and wait for the Windows/Linux/macOS matrix and
CodeQL. Do not dispatch the release workflow with `release=5.2.2` as part of
the PR or merge process.
