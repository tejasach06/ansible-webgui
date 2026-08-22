# Codebase Refactor — Phase 1 (Stabilize & Land WIP) Implementation Plan

> **For agentic workers:** Execute task-by-task, in order. Steps use checkbox (`- [ ]`) syntax for tracking. This phase stabilizes existing uncommitted code (not new-feature TDD) — steps are investigate → run existing test → fix → verify → commit, per task.

**Goal:** Land the currently-uncommitted pipelines/approvals/launch-governance/RBAC-scope/run-report feature on `dev` as a clean, fully-tested, fully-wired commit set, with zero behavior guessed beyond matching documented repo conventions.

**Architecture:** No new architecture — this phase verifies and completes an existing in-flight diff against the conventions already documented in `AGENTS.md` (router/service split, error envelope, audit trail, RBAC dependency pattern, sync/async session split).

**Tech Stack:** FastAPI + Celery + SQLAlchemy 2.0 (backend), React 18.3.1 + TypeScript strict (frontend), pytest 8.3.4 + pytest-asyncio 0.25.3, Podman Compose.

**Spec:** `docs/superpowers/specs/2026-08-17-codebase-refactor-design.md`

## Global Constraints

- No CI, linter, or formatter additions (AGENTS.md convention; explicit user decision).
- Error envelope: `raise HTTPException(status_code=<n>, detail={"code": "<snake_case_code>", "message": "<text>"})`.
- Every mutating endpoint calls `await audit(db, "<action>", actor_user_id=..., object_type=..., object_id=..., detail=...)`.
- Services raise bare `ValueError("<code>")`; routers translate to `HTTPException`. Services never import FastAPI.
- FastAPI routes: `async def` + `AsyncSessionLocal`/`get_db` (asyncpg). Celery tasks: plain `def` + `SyncSessionLocal` (psycopg2), `try/finally: db.close()`.
- RBAC: `Depends(require("<perm>"))` for permissioned routes; permissions registered in `PERMISSIONS` dict in `backend/app/core/rbac.py`.
- Frontend: all HTTP via `apiFetch<T>()` in `frontend/src/lib/api.ts`; never raw `fetch`. Named + default export per page component. Props/payloads typed with `interface`. No React 19 / Tailwind 4 APIs.
- Async tests touching session-scoped fixtures: `@pytest.mark.asyncio(loop_scope="session")`.
- Do not touch Phase 2 (structural refactor) or Phase 3 (Known Gaps) scope — those are separate plans, executed after this one lands.

---

### Task 1: Map the WIP feature and verify wiring

**Files (read only, no edits yet):**
- `backend/app/api/pipelines.py`, `backend/app/services/launch.py`, `backend/app/services/rbac_scope.py`, `backend/app/services/run_report.py`, `backend/app/tasks/run_pipeline.py`, `backend/alembic/versions/0001_workflow_schema.py`
- Modified: `backend/app/api/auth.py`, `api/content/files.py`, `api/credentials.py`, `api/inventories.py`, `api/job_templates.py`, `api/jobs/lifecycle.py`, `api/jobs/queries.py`, `api/jobs/schemas.py`, `api/playbooks.py`, `api/projects.py`, `api/schedules.py`, `core/rbac.py`, `db/models.py`, `db/seed.py`, `main.py`, `services/approvals.py`, `services/job_events.py`, `tasks/run_job.py`, `tasks/worker.py`
- Frontend new: `CredentialsPanel.tsx`, `HostMatrix.tsx`, `MembersPanel.tsx`, `OverrideDiff.tsx`, `PipelinesPanel.tsx`, `SchedulesPanel.tsx`, `ApprovalsPage.tsx`, `PipelineRunPage.tsx`
- Frontend modified: `App.tsx`, `api/jobs.ts`, `AppShell.tsx`, `Can.tsx`, `JobLaunchForm.tsx`, `RunJobDialog.tsx`, `TaskTree.tsx`, `TemplatesPanel.tsx`, `lib/types.ts`, `JobDetailPage.tsx`, `JobsPage.tsx`, `ProjectWorkspacePage.tsx`

**Interfaces:**
- Produces: a written note (top of this task's commit message or a scratch file, not committed) listing: (a) what a "pipeline" is (ordered job-template sequence, stage gating, etc. — read from `run_pipeline.py`/`pipelines.py`), (b) every new permission string introduced, (c) every new endpoint path + method.

- [x] **Step 1: Read all Task 1 files listed above in full.**

- [x] **Step 2: Verify router registration** — confirm `pipelines.router` is included in `backend/app/main.py` alongside the other routers (`app.include_router(...)`). If missing, add it following the exact pattern used for the existing routers in that file.

- [x] **Step 3: Verify permission registration** — for every new permission string referenced via `Depends(require("perm.name"))` in `pipelines.py` (or any modified router), confirm it exists as a key in `PERMISSIONS` in `backend/app/core/rbac.py` for the correct roles. Add any missing entries following the existing dict shape (roles: `admin, manager, developer, operator, viewer`).

- [x] **Step 4: Verify audit calls** — for every mutating endpoint (`POST`/`PUT`/`PATCH`/`DELETE`) in `pipelines.py` and any modified router files, confirm it calls `await audit(db, "<action>", ...)` per the existing pattern in `app/services/audit.py`. Add missing calls; pick action names consistent with existing ones (`job_requested`, `job_approved`, etc. — e.g. `pipeline_requested`, `pipeline_approved`).

- [x] **Step 5: Verify error envelope** — grep `pipelines.py` and modified routers for any `raise HTTPException` not using `detail={"code": ..., "message": ...}`. Fix any that don't match.

- [x] **Step 6: Verify frontend `apiFetch` usage** — grep `frontend/src` for raw `fetch(` calls introduced in the new/modified files from this diff. Replace any with `apiFetch<T>()`.

- [x] **Step 7: Commit nothing yet** — this task is investigation + wiring fixes only. Stage wiring fixes with `git add -p` selectively if trivial (e.g. missing router include), but hold the commit until Task 2's tests pass, so wiring fixes land together with the tests that prove them.

---

### Task 2: Get new backend tests green

**Files:**
- Test: `backend/tests/test_pipelines.py`, `backend/tests/test_launch_governance.py`, `backend/tests/test_project_rbac.py`, `backend/tests/test_run_report.py`
- Modify as needed: `backend/app/api/pipelines.py`, `backend/app/services/launch.py`, `backend/app/services/rbac_scope.py`, `backend/app/services/run_report.py`, `backend/app/tasks/run_pipeline.py`, `backend/app/db/models.py`

**Interfaces:**
- Consumes: wiring fixes from Task 1.
- Produces: all four new test files passing; any function/class signatures they exercise are now stable — later tasks (frontend wiring, Phase 2) must not change these signatures without re-running this suite.

- [x] **Step 1: Run the four new test files.**

Run: `podman compose exec api pytest -q tests/test_pipelines.py tests/test_launch_governance.py tests/test_project_rbac.py tests/test_run_report.py`

Expected: some failures (files are uncommitted WIP) — record exact failure output.

- [x] **Step 2: Fix failures one at a time.** For each failure, read the failing test's assertion, read the implementation it targets, and fix the implementation (not the test, unless the test itself asserts wrong behavior against a documented invariant like `approved_by != requested_by` in `approve_job_run()` — in that case fix the test to match the real invariant). Re-run the single failing test after each fix:

Run: `podman compose exec api pytest -q tests/test_pipelines.py::<test_name> -v`

- [x] **Step 3: Run the full backend suite** to confirm no regression in existing tests from the modified files (`test_approvals.py`, `test_auth.py`, `test_rbac.py`, `test_content_api.py`, `test_job_events.py`, `test_resource_edits.py`).

Run: `podman compose exec api pytest -q`
Expected: PASS, 0 failures.

(If `ansible_webgui_test` database doesn't exist: `podman compose exec postgres sh -c 'createdb -U "$POSTGRES_USER" ansible_webgui_test'` first.)

- [x] **Step 4: Commit.**

```bash
git add backend/app/main.py backend/app/core/rbac.py backend/app/api/pipelines.py \
  backend/app/services/launch.py backend/app/services/rbac_scope.py \
  backend/app/services/run_report.py backend/app/tasks/run_pipeline.py \
  backend/app/db/models.py backend/tests/test_pipelines.py \
  backend/tests/test_launch_governance.py backend/tests/test_project_rbac.py \
  backend/tests/test_run_report.py
git commit -m "feat: add pipelines, launch governance, RBAC scope, run reports"
```

---

### Task 3: Verify and stabilize existing modified backend files

**Files:**
- Modify: `backend/app/api/auth.py`, `api/content/files.py`, `api/credentials.py`, `api/inventories.py`, `api/job_templates.py`, `api/jobs/lifecycle.py`, `api/jobs/queries.py`, `api/jobs/schemas.py`, `api/playbooks.py`, `api/projects.py`, `api/schedules.py`, `services/approvals.py`, `services/job_events.py`, `tasks/run_job.py`, `tasks/worker.py`
- Test: `backend/tests/test_content_api.py`, `test_job_events.py`, `test_rbac.py`, `test_resource_edits.py`

**Interfaces:**
- Consumes: Task 2's stable pipelines/launch/rbac_scope/run_report modules (these files were modified to integrate with them — e.g. `jobs/lifecycle.py` likely now checks pipeline-related state).
- Produces: full existing test suite green with these files' changes included.

- [x] **Step 1: Run the four modified test files against the modified source.**

Run: `podman compose exec api pytest -q tests/test_content_api.py tests/test_job_events.py tests/test_rbac.py tests/test_resource_edits.py -v`

- [x] **Step 2: For each failure, diff the file against git HEAD to see exactly what changed, and confirm the change matches the intent mapped in Task 1** (e.g. `jobs/lifecycle.py` +184 lines likely adds pipeline-stage-aware job launching — confirm it doesn't break single-job launches). Fix regressions; do not revert intentional new behavior.

Run: `git diff HEAD -- backend/app/api/jobs/lifecycle.py`

- [x] **Step 3: Run full backend suite again to confirm everything integrates.**

Run: `podman compose exec api pytest -q`
Expected: PASS, 0 failures.

- [x] **Step 4: Commit.**

```bash
git add backend/app/api/auth.py backend/app/api/content/files.py backend/app/api/credentials.py \
  backend/app/api/inventories.py backend/app/api/job_templates.py backend/app/api/jobs/lifecycle.py \
  backend/app/api/jobs/queries.py backend/app/api/jobs/schemas.py backend/app/api/playbooks.py \
  backend/app/api/projects.py backend/app/api/schedules.py backend/app/services/approvals.py \
  backend/app/services/job_events.py backend/app/tasks/run_job.py backend/app/tasks/worker.py \
  backend/app/db/seed.py backend/tests/test_content_api.py backend/tests/test_job_events.py \
  backend/tests/test_rbac.py backend/tests/test_resource_edits.py
git commit -m "feat: integrate pipeline/RBAC-scope awareness into jobs, projects, credentials APIs"
```

---

### Task 4: Investigate migration squash safety

**Files:**
- Read: `backend/alembic/versions/0001_workflow_schema.py`, `scripts/release-main.sh`, `scripts/seed_podman_demo.py`, any file under `scripts/` or `docs/` referencing `0001_initial_schema`, `0002_global_inventories`, `0003_credential_username`, or `0004_operator_pack`.

**Interfaces:**
- Produces: a go/no-go decision, recorded in the Task 5 commit message.

- [x] **Step 1: Search for references to the deleted migration IDs.**

Run: `grep -rn "0001_initial_schema\|0002_global_inventories\|0003_credential_username\|0004_operator_pack" --include="*.py" --include="*.sh" --include="*.md" .`

- [ ] **Step 2: Decide.** If no references found outside the deleted files themselves, and no deployment docs mention a live database that already ran these migrations, the squash is safe — proceed to Task 5. If any reference is found, STOP: do not delete the old migrations. Instead, report the exact reference found back to the user before continuing (do not decide unilaterally).

---

### Task 5: Final verification and frontend build

**Files:**
- Build: `frontend/` (all frontend files from the diff)

**Interfaces:**
- Consumes: stable backend from Tasks 2-4.
- Produces: a green full-stack build, ready for Phase 2 to start from.

- [ ] **Step 1: Frontend typecheck.**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. Fix any type errors in the modified/new frontend files, matching `interface`-typed props convention.

- [ ] **Step 2: Frontend build.**

Run: `cd frontend && npm run build`
Expected: exit 0.

- [ ] **Step 3: Full backend suite one more time (regression check after any Step 1 fixes touched shared types).**

Run: `podman compose exec api pytest -q`

- [ ] **Step 4: Commit frontend.**

```bash
git add frontend/src
git commit -m "feat: add pipelines/approvals/members/credentials UI panels"
```

- [ ] **Step 5: Rebuild and smoke-check the stack.**

Run: `podman compose up -d --build`
Then browser-smoke: log in, open a project, confirm the new Pipelines/Approvals/Members panels render without console errors.

---

## Self-Review Notes

- **Spec coverage:** Tasks 1-5 cover every file and step listed under "Phase 1" in the design spec, including the migration-squash safety check (Task 4) and full test/build verification (Task 5).
- **Placeholder scan:** no TBD/TODO; every step has an exact command or exact file list. Task 1's "map the feature" step is investigation-only by design (reverse-engineering existing code, not writing new code from a spec), which is why it has no code block — it precedes and informs Tasks 2-3's fixes.
- **Type consistency:** N/A at plan-authoring time — the actual signatures live in the uncommitted diff itself, not invented here; Task 2/3 explicitly instruct matching existing signatures rather than declaring new ones.

## Execution Handoff

This plan is handed to the `prime-agent` CLI for execution, task-by-task, with backend-pytest and frontend-tsc as autonomous completion gates. Phase 2 and Phase 3 plans will be written after Phase 1 lands and its actual resulting file sizes/wiring are known (Phase 2's target file list depends on Phase 1's final line counts).
