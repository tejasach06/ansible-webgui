# Contributing

## Prerequisites

- Podman with `podman compose`.
- Node 22, matching `Containerfile.web`.
- Python 3.12 only when working outside containers.

## Local setup

```sh
cp .env.example .env
podman compose up -d --build
cd frontend && npm ci && npm run dev
```

## Layout

- `backend/app/api/` — one router module per resource; HTTP layer only.
- `backend/app/core/` — config, JWT, password hashing, RBAC.
- `backend/app/db/` — SQLAlchemy models, sessions, seed, base.
- `backend/app/services/` — domain rules: approvals, audit, content, credentials.
- `backend/app/tasks/` — Celery app, runner task, prune stub.
- `backend/alembic/` — migrations.
- `backend/tests/` — pytest suite, excluded from images.
- `frontend/src/` — SPA source.

## Coding conventions

- Routers stay HTTP-only; business rules live in `app/services/`.
- Services raise `ValueError("<code>")`; routers translate to `HTTPException(status_code=..., detail={"code", "message"})`.
- Pydantic request models stay inline in router modules; do not add a `schemas/` package.
- Do not add `response_model=`; responses are hand-built dicts.
- Permissions live only in `PERMISSIONS` in `app/core/rbac.py`.
- FastAPI uses async `AsyncSessionLocal`; Celery uses sync `SyncSessionLocal` and must not call `asyncio.run()`.
- Frontend HTTP must go through `apiFetch` in `frontend/src/lib/api.ts`.
- Dependencies are exact pins: `==` in `backend/pyproject.toml`, no `^` in `package.json`.
- No formatter or linter is configured; match the edited file and do not reflow unrelated code.

## Tests

```sh
podman compose exec api pytest -q
cd frontend && npx tsc --noEmit && npm run build
```

Backend tests need Postgres reachable as host `postgres` with database `ansible_webgui_test`. Async tests touching session-scoped fixtures must use `@pytest.mark.asyncio(loop_scope="session")`; pytest-asyncio 0.25.3 has no `asyncio_default_test_loop_scope`. Copy `backend/tests/test_approvals.py` patterns.

## Dependency changes

Run backend `pip-audit` and frontend `npm audit` when dependencies change.

## Commits and PRs

Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`). Keep one logical change per PR. PR bodies must state what changed, why, and verification commands with output. Changes to auth, approvals, credentials, or the job runner must call out the security invariant touched.

## Do-not-break invariants

1. `approved_by != requested_by` for live runs — enforced in `approve_job_run()` at `backend/app/services/approvals.py`, raising `ValueError("self_approval_forbidden")`.
2. Live jobs execute an exported `git archive <git_sha>`, never the mutable working tree — `backend/app/tasks/run_job.py` uses `Repo(proj_git).archive(f, format="tar", treeish=sha)` then extracts into `<temp_dir>/project`.
3. Credentials are Fernet-encrypted at rest and decrypted only into an ephemeral `0700` dir for the task lifetime — `tempfile.mkdtemp(dir=settings.ARTIFACT_ROOT)` + `os.chmod(temp_dir, 0o700)`, key files `0600`, `shutil.rmtree(temp_dir)` in `finally`.
4. Git on disk (`CONTENT_ROOT=/data/content`) is the source of truth for playbooks, roles, inventories.
5. Auth is HttpOnly cookies only — never localStorage, never a URL token.
6. Every mutating REST call carries `X-Requested-With: XMLHttpRequest` — checked by `require_csrf()` in `backend/app/api/auth.py:45`, 403 `csrf_missing` otherwise.

Deep internal reference lives in [AGENTS.md](AGENTS.md).
