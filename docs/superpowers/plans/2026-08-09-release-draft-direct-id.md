# Release Draft Direct-ID Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make release verification consume the authoritative numeric ID returned when the draft is created.

**Architecture:** The write-token draft job creates the draft with `gh api`, validates and emits the returned ID, uploads assets through the existing GitHub CLI command, then verifies the stored draft by direct numeric lookup. The isolated attestation and publication jobs remain unchanged.

**Tech Stack:** GitHub Actions YAML, GitHub CLI, GitHub REST API, Bash, jq, Python unittest contracts.

## Global Constraints

- Keep version `5.2.2` unchanged.
- Preserve exact job permissions and full-SHA-pinned attestation action.
- Add no action, dependency, token, retry, sleep, or workflow artifact.
- Release failures remain fail closed with the release left as a draft.

---

### Task 1: Enforce authoritative release-ID flow

**Files:**
- Modify: `tests/test_ci.py`
- Modify: `.github/workflows/Cats Tests.yml`

**Interfaces:**
- Consumes: the JSON release object returned by `POST /repos/${GITHUB_REPOSITORY}/releases`.
- Produces: `steps.created_release.outputs.release_id`, consumed by stored-release verification.

- [x] **Step 1: Write the failing contract test**

Require the create step to have `id: created_release`, call the release REST
endpoint, validate the returned numeric ID, and write it to `GITHUB_OUTPUT`.
Require stored verification to consume that output and reject collection-based
draft rediscovery.

- [x] **Step 2: Run the focused test to verify RED**

Run: `python -m unittest tests.test_ci.WorkflowPolicyTests -v`

Expected: failure because the current workflow uses `gh release create` and a
paginated releases-list lookup.

- [x] **Step 3: Implement the minimal workflow change**

Use a Bash run block to build the release request with `jq -n`, call `gh api
--method POST`, extract and validate `.id`, and emit `release_id`. Add the
captured ID to the verification environment, validate it, and call the direct
release resource. Delete only the post-create list rediscovery.

- [x] **Step 4: Run focused and complete CI contracts**

Run:

```text
python -m unittest tests.test_ci.WorkflowPolicyTests -v
python -m unittest tests.test_ci -v
```

Expected: all tests pass.

- [x] **Step 5: Review and verify**

Run `git diff --check`, inspect the complete branch diff and status, and confirm
the permissions/action contracts remain unchanged.

### Task 2: Record the completed branch state

**Files:**
- Modify: `docs/HANDOFF.md`
- Delete after the milestone commit: this design and plan document.

**Interfaces:**
- Produces: a current handoff describing the failure, fix, validation, hosted
  limitation, and next action.

- [x] **Step 1: Update the handoff**

Replace stale PR #4 state with merged main commit `cfae36c`, hosted run
`31307655995`, the direct-ID correction, verification evidence, and the
requirement for PR review before another release attempt.

- [ ] **Step 2: Commit the implementation milestone**

Stage only the workflow, contract, design, plan, and handoff files; review the
staged diff; then create a coherent verified commit.

- [ ] **Step 3: Remove in-flight design artifacts**

Delete the design and plan after the implementation milestone is committed,
verify the deletion, and commit the required cleanup so Git history retains the
approved rationale without leaving superseded in-flight documents on the
branch tip.
