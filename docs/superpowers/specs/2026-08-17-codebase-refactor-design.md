# Ansible WebGUI — Codebase Refactor Design

Date: 2026-08-17
Status: Approved for implementation planning

## Context

The working tree on `dev` carries a large uncommitted diff (40 files, +1576/-711)
plus several new untracked files. This is a half-finished, unspecced feature —
a "pipelines / approvals / launch governance / RBAC scope / run reports"
subsystem — layered on top of the existing job-run flow described in
`AGENTS.md`. Alembic migrations `0001`–`0004` were deleted and replaced with a
single new `0001_workflow_schema.py`, i.e. a migration squash bundled into the
same diff.

Goal: don't do a big-bang "refactor everything" pass. Instead:
1. Finish and land the in-progress feature safely (it's closer to "done" than
   "started" — 882 new lines, 4 new test files already exist).
2. Only then do a behavior-preserving structural cleanup, scoped to files that
   violate the repo's own documented conventions (router/service split) or
   have grown oversized as a result of phase 1.
3. Close the specific, named "Known Gaps" from `AGENTS.md` that are functional
   stubs (`prune.py`), not tooling gaps.

Explicitly out of scope (per user decision): adding CI, linters, or
formatters. `AGENTS.md` currently states none exist and instructs not to add
one unprompted — that instruction stands.

## Non-goals

- No framework swap (FastAPI/Celery/React/Podman stack unchanged).
- No new CI/lint/formatter tooling.
- No DB engine change.
- No auth model change (HttpOnly cookie JWT stays).
- No speculative abstraction — every extraction in Phase 2 must have a
  concrete duplicated/oversized-file justification, not "might be reused".

## Phase 1 — Stabilize & land WIP

**Scope:** every file currently modified or untracked in `git status` on `dev`.

Backend, new:
- `backend/app/api/pipelines.py` (369 lines)
- `backend/app/services/launch.py`
- `backend/app/services/rbac_scope.py`
- `backend/app/services/run_report.py`
- `backend/app/tasks/run_pipeline.py`
- `backend/alembic/versions/0001_workflow_schema.py` (replaces deleted 0001-0004)
- `backend/tests/test_launch_governance.py`, `test_pipelines.py`,
  `test_project_rbac.py`, `test_run_report.py`

Backend, modified: `api/auth.py`, `api/content/files.py`, `api/credentials.py`,
`api/inventories.py`, `api/job_templates.py`, `api/jobs/lifecycle.py`,
`api/jobs/queries.py`, `api/jobs/schemas.py`, `api/playbooks.py`,
`api/projects.py`, `api/schedules.py`, `core/rbac.py`, `db/models.py`,
`db/seed.py`, `main.py`, `services/approvals.py`, `services/job_events.py`,
`tasks/run_job.py`, `tasks/worker.py`, plus matching test files.

Frontend, new: `CredentialsPanel.tsx`, `HostMatrix.tsx`, `MembersPanel.tsx`,
`OverrideDiff.tsx`, `PipelinesPanel.tsx`, `SchedulesPanel.tsx`,
`ApprovalsPage.tsx`, `PipelineRunPage.tsx`.

Frontend, modified: `App.tsx`, `api/jobs.ts`, `AppShell.tsx`, `Can.tsx`,
`JobLaunchForm.tsx`, `RunJobDialog.tsx`, `TaskTree.tsx`, `TemplatesPanel.tsx`
(+298 lines), `lib/types.ts`, `JobDetailPage.tsx`, `JobsPage.tsx`,
`ProjectWorkspacePage.tsx`.

**Steps:**
1. Read every changed/new file in full; build a map of what the feature
   actually does (pipeline = ordered sequence of job templates? approval gate
   before pipeline stages? what does `rbac_scope.py` add beyond
   `core/rbac.py`'s existing permission table?).
2. Check wiring completeness: is `pipelines.py` router registered in
   `main.py`? Are new permission strings added to `PERMISSIONS` in
   `core/rbac.py`? Does every new mutating endpoint call `audit(...)`? Does
   every new endpoint use the existing error envelope
   (`HTTPException(status_code=.., detail={"code":.., "message":..})`)?
   Does frontend use `apiFetch` exclusively (no raw `fetch`)?
3. Run existing new tests as-is (`podman compose exec api pytest -q`) to find
   what's already broken vs. already passing.
4. Fix broken wiring and finish anything half-done, matching existing
   conventions exactly (sync/async session split, `Mapped[...]` model style,
   RBAC `Depends(require(...))` pattern, named Celery tasks).
5. Migration squash: confirm no real/deployed DB depends on old
   `0001`–`0004` revision IDs (check for any deployment docs/scripts
   referencing them, e.g. `scripts/release-main.sh`, README). If none found,
   keep the squash as-is and document it as intentional in the commit
   message. If found, this becomes a blocking question back to the user
   before Phase 1 can complete.
6. Get full backend test suite green, `npx tsc --noEmit && npm run build`
   clean, `podman compose up -d --build` sane.
7. Commit in logical, feature-scoped commits (not "WIP" or "refactor").

**Acceptance:** `pytest -q` all green including the 4 new test files;
frontend build clean; every new endpoint reachable and exercised by at least
one test or a documented browser-smoke; migration history intentional and
consistent; nothing left uncommitted.

## Phase 2 — Structural refactor (behavior-preserving)

**Trigger for inclusion:** file violates AGENTS.md's own "business rules live
in services/, not routers" convention, or has grown large as a *direct
result* of Phase 1 changes. Starting candidates (line counts as of this
diff, to be re-measured after Phase 1 lands):
- `api/pipelines.py` (369) — audit for logic that belongs in a
  `services/pipelines.py`.
- `api/jobs/lifecycle.py` (328, +184 in this diff)
- `db/models.py` (310, +124 in this diff) — confirm this is still pure model
  declarations, no logic creep.
- `api/projects.py` (232, +121 in this diff)
- `frontend/src/components/TemplatesPanel.tsx` (+298 in this diff) — check
  for multiple concerns bundled into one component.

**Rules:**
- Pure extraction/move, no behavior change. Every extracted unit keeps
  identical inputs/outputs; existing tests pass unchanged (no test edits
  except import paths).
- No new abstraction layers, no interfaces-for-one-implementation, no config
  for values that don't vary.
- Each extraction is its own commit for easy review/revert.
- Frontend: confirm 100% `apiFetch` usage, `interface`-typed props/payloads,
  named+default export pattern for pages — fix stragglers found during audit.

**Acceptance:** identical test suite passes before/after each extraction;
line counts of the flagged files drop below ~250 (router files) via extracted
services, with no net new file unless splitting a proven mixed-concern
module.

## Phase 3 — Close named Known Gaps

From `AGENTS.md` "Known Gaps", functional items only (tooling gaps
explicitly excluded per user decision):

1. **`backend/app/tasks/prune.py::prune_old_data()`** — currently `pass`.
   This is a new feature, not cleanup, so before implementing: define
   retention policy as a `Settings` field (e.g. `ARTIFACT_RETENTION_DAYS`,
   `JOB_EVENT_RETENTION_DAYS`), delete `JobRun`/`JobEvent` rows and
   `ARTIFACT_ROOT` temp dirs older than the window, wire into `beat`
   schedule or leave as an on-demand Celery task if no existing scheduled-task
   pattern fits. This sub-decision needs a short confirmation with the user
   before implementation (policy defaults, whether it's beat-scheduled) —
   flagged as a checkpoint in the implementation plan, not decided here.
2. **`app/main.py` deprecated `@app.on_event("startup")`** — replace with
   `lifespan` async context manager per current FastAPI convention; startup
   seeding behavior (`seed_roles_and_admin()` on every boot) unchanged.
3. **Frontend scaffold gap** (`tailwind.config.js`, `postcss.config.js`, no
   global CSS despite `tailwindcss` being installed) — reassess at Phase 3
   start against whatever styling convention Phase 1's new panels actually
   used (inline styles, per current `App.tsx`/`AppShell.tsx` pattern, per
   `AGENTS.md`'s "Known Gaps" note). If Phase 1 components already
   established a consistent inline-style convention, wiring Tailwind now
   would introduce a second styling system — decide based on actual Phase 1
   outcome, not assumed upfront.

**Explicitly not touched:** no CI workflow, no ruff/eslint/prettier, no
coverage config — AGENTS.md's "none configured, don't add one unprompted"
stands.

## Verification (every phase)

- `podman compose exec api pytest -q`
- `cd frontend && npx tsc --noEmit && npm run build`
- Browser-smoke any touched UI flow (new panels/pages) via the `browser` tool
- `xd://graphify_update` after each phase (repo tooling policy); fallback to
  key-free rebuild (`graphify extract . --code-only && graphify cluster-only
  . --no-label`) if it reports a 0-node graph
- `pip-audit` / `npm audit` only if Phase 1 or Phase 3 change dependencies

## Risks

- Migration squash (0001-0004 → new 0001) could break any environment that
  already applied old migrations. Mitigated by explicit check in Phase 1
  step 5 before proceeding.
- Reverse-engineering unspecced WIP risks guessing wrong on intent for edge
  cases (e.g. approval semantics for pipelines vs. single jobs). Mitigated by
  matching the *existing* single-job approval invariant
  (`approved_by != requested_by`) as the default assumption unless the diff
  clearly does otherwise, and flagging ambiguity back to the user during
  implementation rather than guessing silently.
- Phase 2 extractions could accidentally change async/sync session usage
  (FastAPI async vs. Celery sync split) — mitigated by keeping extracted
  services in the same router file's execution context, not moving
  await-based code into Celery-task-only modules or vice versa.

## Execution mechanism

Per user instruction, implementation phases are executed via the
`prime-agent` CLI (available on `PATH`), invoked with full tool and skill
access (`-p` print mode for headless runs, `--tools`/`--skill` unrestricted,
`--goal` set to the phase's acceptance criteria), from within this
conversation's orchestration. Each phase's `prime-agent` invocation runs
against this repo's working directory, and its result is verified via the
commands above before moving to the next phase.
