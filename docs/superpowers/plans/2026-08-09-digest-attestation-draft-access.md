# Digest-Based Draft Release Attestation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CATS attest the already-verified 5.2.2 release ZIP name and digest without granting the attestation job access to the unpublished draft.

**Architecture:** Keep both release-write jobs action-free and keep their stored-asset byte verification unchanged. Delete the impossible read-only draft lookup from `attest_release` and pass the validated `draft_release` archive name and SHA-256 directly to the pinned action through its native `subject-name` and `subject-digest` inputs.

**Tech Stack:** GitHub Actions YAML, `actions/attest` v4.2.2 pinned to `1e69f48acb82d1966a394da916b4c1698aa569d6`, Python `unittest`, Blender 5.2 extension tooling.

## Global Constraints

- Keep CATS at final version `5.2.2`; do not change version metadata.
- Keep `draft_release` and `publish_release` action-free with only `contents: write`.
- Keep `attest_release` permissions exactly `contents: read`, `id-token: write`, and `attestations: write`.
- Keep the exact reviewed `actions/attest` full-commit pin.
- Attest only `cats_blender_plugin-<version>.zip` by its validated name and SHA-256.
- Preserve `draft_release -> attest_release -> publish_release` fail-closed ordering.
- Preserve numeric release/asset identity and stored-byte verification in both write-capable jobs.
- Add no PAT, GitHub App token, workflow-artifact transfer, action, dependency, recovery mode, or automatic publication.
- Do not delete, modify, publish, or reuse failed draft release ID `367427437`.
- Do not push, open a pull request, rerun the release, tag, or publish without separate authorization.

---

### Task 1: Replace the inaccessible draft download with digest attestation

**Files:**
- Modify: `tests/test_ci.py`
- Modify: `.github/workflows/Cats Tests.yml`

**Interfaces:**
- Consumes: `draft_release.outputs.archive_name` and `draft_release.outputs.sha256`, both emitted only after the write job verifies the stored numeric draft asset.
- Produces: one attestation subject named by `archive_name` with digest `sha256:<sha256>`; `publish_release` remains gated on the action's success.

- [ ] **Step 1: Add the focused failing contract**

Add this method to `WorkflowPolicyTests` before changing the workflow:

```python
def test_attestation_uses_verified_digest_without_draft_access(self):
    attest = workflow_job(self.workflow, "attest_release")

    self.assertNotIn("gh api", attest)
    self.assertNotIn("GH_TOKEN:", attest)
    self.assertNotIn("releases/${RELEASE_ID}", attest)
    self.assertNotIn("releases/assets/${ASSET_ID}", attest)
    self.assertNotIn("sha256sum", attest)
    self.assertIn(
        "subject-name: ${{ needs.draft_release.outputs.archive_name }}",
        attest,
    )
    self.assertIn(
        "subject-digest: sha256:${{ needs.draft_release.outputs.sha256 }}",
        attest,
    )
    self.assertEqual(1, attest.count("subject-name:"))
    self.assertEqual(1, attest.count("subject-digest:"))
    self.assertNotIn("subject-path:", attest)
    self.assertNotIn("subject-checksums:", attest)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -m unittest `
  tests.test_ci.WorkflowPolicyTests.test_attestation_uses_verified_digest_without_draft_access `
  -v
```

Expected: FAIL because the current attestation job contains `gh api` and uses
`subject-path` instead of the required name/digest inputs.

- [ ] **Step 3: Update the existing cross-job contract to match the approved boundary**

In `test_release_jobs_bind_and_reverify_the_stored_primary_zip`, preserve the
exact output allowlist and change propagation checks so every output is still
required in `draft_release` and `publish_release`, while only `archive_name` and
`sha256` are required in `attest_release`:

```python
for output in ("tag", "archive_name", "sha256", "release_id", "asset_id"):
    self.assertIn(f"      {output}: ${{{{ steps.", draft)
    self.assertIn(f"needs.draft_release.outputs.{output}", publish)
for output in ("archive_name", "sha256"):
    self.assertIn(f"needs.draft_release.outputs.{output}", attest)
for output in ("tag", "release_id", "asset_id"):
    self.assertNotIn(f"needs.draft_release.outputs.{output}", attest)
```

Keep draft numeric-ID ordering checks. Apply downstream numeric-ID and
download/hash ordering checks only to `publish_release`:

```python
self.assertIn("releases/assets/${ASSET_ID}", publish)
self.assertIn("sha256sum", publish)
self.assertLess(
    publish.index('[[ "${RELEASE_ID}" =~ ^[0-9]+$ ]]'),
    publish.index("releases/${RELEASE_ID}"),
)
self.assertLess(
    publish.index('[[ "${ASSET_ID}" =~ ^[0-9]+$ ]]'),
    publish.index("releases/assets/${ASSET_ID}"),
)
self.assertLess(
    publish.index('test "${actual_sha256}" = "${EXPECTED_SHA256}"'),
    publish.index("-F draft=false"),
)
```

Remove old assertions requiring an attestation-job release URL, asset URL,
`sha256sum`, `subject-path`, or digest-before-action shell ordering. Preserve:

```python
self.assertIn("releases/${RELEASE_ID}", publish)
self.assertIn("-F draft=false", publish)
self.assertNotIn("actions/upload-artifact", draft + attest + publish)
self.assertNotIn("actions/download-artifact", draft + attest + publish)
```

- [ ] **Step 4: Run the affected contracts and confirm they remain RED for the intended production gap**

Run:

```powershell
python -m unittest `
  tests.test_ci.WorkflowPolicyTests.test_release_jobs_bind_and_reverify_the_stored_primary_zip `
  tests.test_ci.WorkflowPolicyTests.test_attestation_uses_verified_digest_without_draft_access `
  -v
```

Expected: failures caused by the current attestation download and
`subject-path`; no parser or test-code errors.

- [ ] **Step 5: Apply the smallest workflow correction**

Replace the entire `attest_release` `defaults` and `steps` tail with this single
action step; leave its condition, dependency, runner, timeout, and permissions
unchanged:

```yaml
    steps:
      - name: Attest verified release digest
        uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6
        with:
          subject-name: ${{ needs.draft_release.outputs.archive_name }}
          subject-digest: sha256:${{ needs.draft_release.outputs.sha256 }}
```

Do not change `draft_release`, `publish_release`, global permissions, release
conditions, environment placement, or version metadata.

- [ ] **Step 6: Verify focused and full GREEN**

Run:

```powershell
python -m unittest `
  tests.test_ci.WorkflowPolicyTests.test_release_jobs_isolate_write_tokens_from_actions `
  tests.test_ci.WorkflowPolicyTests.test_release_jobs_bind_and_reverify_the_stored_primary_zip `
  tests.test_ci.WorkflowPolicyTests.test_attestation_uses_verified_digest_without_draft_access `
  -v
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
git diff --check
```

Expected: all focused contracts and the full CI suite pass; compilation and
diff checks report no errors.

- [ ] **Step 7: Review and commit the production/test unit**

Inspect:

```powershell
git diff -- '.github/workflows/Cats Tests.yml' tests/test_ci.py
git status --short
```

Confirm the workflow diff deletes code from the attestation job, adds only the
two native subject inputs, and leaves both write jobs unchanged. Then commit:

```powershell
git add -- '.github/workflows/Cats Tests.yml' tests/test_ci.py
git diff --cached --check
git diff --cached
git commit -m "ci: attest verified release digest"
```

---

### Task 2: Review and verify the fix branch

**Files:**
- Inspect: `.github/workflows/Cats Tests.yml`
- Inspect: `tests/test_ci.py`
- Generated and ignored: `.packaged-releases/cats_blender_plugin-5.2.2-*.zip`
- Generated and ignored: `.test-runtime/`

**Interfaces:**
- Consumes: the committed workflow/test unit from Task 1.
- Produces: independent review results and exact local package validation evidence without changing GitHub release state.

- [ ] **Step 1: Review the complete branch diff**

Run:

```powershell
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- '.github/workflows/Cats Tests.yml' tests/test_ci.py
git status --short
```

Verify the exact job permissions, pinned action SHA, name/digest expressions,
action-free write jobs, output binding, publication dependency, absence of
draft API access in `attest_release`, and unchanged version `5.2.2`.

- [ ] **Step 2: Request independent correctness/security review**

Use `superpowers:requesting-code-review` against `origin/main..HEAD`. Require
the reviewer to check credential isolation, expression safety, action input
support, output binding, ordering, test strength, and scope. Use
`superpowers:receiving-code-review` before acting on any finding. Accepted
findings require their own focused RED/GREEN cycle and commit.

- [ ] **Step 3: Run local source and package gates with an isolated Blender profile**

Set `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS`, and
`BLENDER_USER_DATAFILES` to task-specific directories under `.test-runtime/`,
then run:

```powershell
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --command extension validate .
python scripts/build.py --blend `
  'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
```

Select the generated
`.packaged-releases/cats_blender_plugin-5.2.2-<shortsha>.zip`, then run:

```powershell
python tests/verify_package.py $Package.FullName --source-dir .
Get-FileHash -Algorithm SHA256 $Package.FullName
git diff --check
git status --short
```

Record the exact package path, SHA-256, member count, Python module count, and
clean tracked status. Do not stage generated output.

---

### Task 3: Final handoff and document retirement

**Files:**
- Modify: `docs/HANDOFF.md`
- Delete: `docs/superpowers/specs/2026-08-09-digest-attestation-draft-access-design.md`
- Delete: `docs/superpowers/plans/2026-08-09-digest-attestation-draft-access.md`

**Interfaces:**
- Consumes: the reviewed implementation commit and exact verification evidence.
- Produces: a review-ready branch with durable incident/fix evidence and no superseded in-flight documents.

- [ ] **Step 1: Update the handoff with completed evidence**

Record all of the following in `docs/HANDOFF.md`:

- branch base, purpose, and implementation commit;
- run `31304178838` root cause and fail-closed outcome;
- digest-based attestation data flow and unchanged job permissions;
- why full-SHA pinning still requires job isolation;
- RED/GREEN contract results, independent review, local commands, package path,
  SHA-256, file/module counts, and clean status;
- hosted checks still required for OIDC, attestation persistence, digest-based
  verification, and final publication;
- failed draft release ID `367427437` remains preserved and requires separate
  deletion authorization;
- next action is authorization to push/open a draft PR, not release recovery.

- [ ] **Step 2: Retire the completed design and plan**

Delete the two in-flight files listed above with `apply_patch`. Git history
retains the approved design and plan.

- [ ] **Step 3: Commit the handoff**

Run:

```powershell
git add -- docs/HANDOFF.md `
  docs/superpowers/specs/2026-08-09-digest-attestation-draft-access-design.md `
  docs/superpowers/plans/2026-08-09-digest-attestation-draft-access.md
git diff --cached --check
git diff --cached
git commit -m "docs: hand off digest attestation fix"
```

- [ ] **Step 4: Run verification-before-completion on final HEAD**

With the isolated Blender environment still set, run:

```powershell
python -m unittest tests.test_ci -v
python -W ignore::SyntaxWarning -m compileall -q -f `
  __init__.py globs.py extentions.py updater.py tools ui extern_tools tests
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --command extension validate .
python scripts/build.py --blend `
  'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
git diff --check
git status --short
git log --oneline origin/main..HEAD
```

Expected: all tests and validations pass, the exact-final-commit package is
verified, and the tracked worktree is clean.

- [ ] **Step 5: Stop for publication and recovery authorization**

Do not push or open a pull request automatically. Report the local branch as
ready and request authorization. Even after the fix PR is merged, do not delete
draft `367427437` or rerun `release=5.2.2` without explicit authorization.
