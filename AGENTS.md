# Repository Guidelines

## Project Overview

Ansible WebGUI is a web control plane for running Ansible playbooks with git-pinned execution, RBAC, two-person approval, and live log streaming.

Stack: FastAPI + Celery backend (Python >=3.12), React/Vite SPA, PostgreSQL 16, Redis 7, run under Podman Compose (`compose.yaml`, `Containerfile.backend`, `Containerfile.web`).

Invariants:
1. `approved_by != requested_by` for live runs — enforced in `approve_job_run()` at `backend/app/services/approvals.py`, raising `ValueError("self_approval_forbidden")`.
2. Live jobs execute an exported `git archive <git_sha>`, never the mutable working tree — `backend/app/tasks/run_job.py` uses `Repo(proj_git).archive(f, format="tar", treeish=sha)` then extracts into `<temp_dir>/project`.
3. Credentials are Fernet-encrypted at rest and decrypted only into an ephemeral `0700` dir for the task lifetime — `tempfile.mkdtemp(dir=settings.ARTIFACT_ROOT)` + `os.chmod(temp_dir, 0o700)`, key files `0600`, `shutil.rmtree(temp_dir)` in `finally`.
4. Git on disk (`CONTENT_ROOT=/data/content`) is the source of truth for playbooks, roles, inventories.
5. Auth is HttpOnly cookies only — never localStorage, never a URL token.
6. Every mutating REST call carries `X-Requested-With: XMLHttpRequest` — checked by `require_csrf()` in `backend/app/api/auth.py:45`, 403 `csrf_missing` otherwise.

## Architecture & Data Flow

Services:

| Name | Command | Purpose |
| --- | --- | --- |
| api | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000` | Serves REST + SSE on `8000:8000`. Never executes Ansible, never decrypts credentials. |
| worker | `celery -A app.tasks.worker worker --loglevel=info -c 4` | Runs `ansible-runner`; the only place credentials are decrypted. |
| beat | `celery -A app.tasks.worker beat -S redbeat.RedBeatScheduler --loglevel=info` | Runs scheduled jobs through RedBeat. |
| web | `nginx -g 'daemon off;'` | Port `8080:80`, serves the built SPA and proxies `/api` to `api` via `nginx.conf`. |
| postgres | `postgres:16-alpine` | PostgreSQL store, volume `pgdata`. |
| redis | `redis:7-alpine` | Celery broker + pub/sub bus. |

Shared volumes: `content:/data/content`, `artifacts:/data/artifacts`, `sshdata:/home/runner/.ssh`.

Compose quirk: `api`/`worker`/`beat` use plain `depends_on` without `condition: service_healthy`; `api` self-waits with an inline `until pg_isready ...; do sleep 1; done` loop. Copy that manual-retry pattern rather than adding health conditions.

Job lifecycle:

```text
POST /api/jobs  (app/api/jobs.py:request_job)
  -> resolve playbook/inventory/project, read HEAD sha via GitPython
  -> 409 template_busy if a live run of the same template is queued/running
  -> freeze_params_snapshot(...)  [app/services/approvals.py]  -> JobRun.params_snapshot (incl. git_sha)
  -> status = pending_approval, or queued when mode=check or template.requires_approval is False
POST /api/jobs/{id}/approve  -> approve_job_run() -> status=queued -> run_job.delay(job.id)
Celery run_job  [app/tasks/run_job.py]  -> status=running
  -> mkdtemp 0700 -> git archive sha -> extract -> symlink galaxy_roles/collections
  -> decrypt credentials into env/ (ssh_key 0600, passwords JSON, vault_pw file)
  -> ansible_runner.run(private_data_dir=temp_dir, project_dir=..., event_handler, cancel_callback)
  -> event_handler: JobEvent rows flushed via bulk_save_objects every 50; each event also
    redis_client.publish(f"job:{id}", {counter, stdout, event})
  -> final status from runner.status/rc; temp_dir removed in finally
GET /api/jobs/{id}/events/stream  -> replays JobEvent rows where counter > after_counter,
  then subscribes to Redis channel job:{id}; StreamingResponse media_type="text/event-stream";
  emits ": heartbeat\n\n" on 15s pubsub timeout; breaks on request.is_disconnected()
POST /api/jobs/{id}/cancel  -> sets redis key job:{id}:cancel=1 (polled by cancel_callback);
  revokes the Celery task when still queued
```

Caps implementers must not silently change: `event_counter > 200000` events are dropped, `stdout` is truncated at 65536 chars with `"\n...[truncated]"`, and list endpoints clamp `limit` to `min(limit, 200)`.

## Key Directories

- `backend/app/api/` — one router module per resource (`auth, users, credentials, projects, playbooks, inventories, job_templates, jobs, content, schedules`). HTTP layer only.
- `backend/app/core/` — `config.py` (pydantic-settings), `auth.py` (JWT encode/decode), `security.py` (argon2), `rbac.py` (permission table).
- `backend/app/db/` — `models.py` (SQLAlchemy 2.0 declarative), `session.py` (async + sync engines), `seed.py`, `base.py`.
- `backend/app/services/` — reusable domain logic: `approvals.py`, `audit.py`, `content.py`, `credentials.py`. Business rules live here, not in routers.
- `backend/app/tasks/` — `worker.py` (Celery app), `run_job.py`, `prune.py`.
- `backend/alembic/` — migrations, `versions/0001_initial_schema.py`.
- `backend/tests/` — pytest suite, excluded from images via `.dockerignore`.
- `frontend/src/` — SPA source; currently only `main.tsx`, `App.tsx`, `lib/api.ts`.
- `graphify-out/` — generated code graph; gitignored (`.gitignore` contains only `graphify-out/`).

## Development Commands

Run from repo root unless noted:

```sh
podman compose up -d --build          # build + start the whole stack
podman compose logs -f api worker     # tail
podman compose exec api pytest -q     # backend tests (see Testing)
podman compose exec api alembic upgrade head
podman compose exec api alembic revision --autogenerate -m "add x"
podman compose down                   # add -v to also drop pgdata/content/artifacts
cd frontend && npm ci && npm run build   # tsc && vite build
cd frontend && npm run dev            # Vite dev server :3000, proxies /api -> localhost:8000
cd frontend && npx tsc --noEmit       # typecheck only
podman compose exec api pip-audit     # dependency CVE audit (pip-audit==2.8.0 is a dev dep)
cd frontend && npm audit
```

`npm run dev|build|preview` are the only three npm scripts. There is no `lint` or `test` script. There is no Makefile, no `scripts/`, and no `.github/workflows`.

## Code Conventions & Common Patterns

Backend:
- Every route handler is `async def`. Routers use `router = APIRouter(prefix="/api/<resource>", tags=["<resource>"])`; `auth.py` is the exception with `prefix="/api"`.
- Request bodies are Pydantic v2 `BaseModel` classes declared inline in the router module, e.g. `JobRequest`, `ApproveRequest` in `api/jobs.py`. There is no `schemas/` package — do not create one.
- Responses are hand-built `dict`s; `response_model=` is not used. Match surrounding style.
- Error envelope is load-bearing. Always `raise HTTPException(status_code=<n>, detail={"code": "<snake_case_code>", "message": "<human text>"})`. The global handler in `app/main.py` (`generic_exception_handler`) and frontend `apiFetch` both read `detail.code` / `detail.message`. Existing codes: `playbook_not_found`, `inventory_not_found`, `job_not_found`, `template_busy`, `self_approval_forbidden`, `bad_state`, `csrf_missing`.
- Services raise bare `ValueError("<code>")`; routers translate that string to an `HTTPException` (see `approve_job` in `api/jobs.py`). Keep that split — services never import FastAPI.
- Auth/RBAC via dependencies only: `user: User = Depends(require("job.approve"))` for permissioned routes, `Depends(get_current_user)` when any authenticated user may call. The SSE stream uses this. Both live in `app/api/auth.py`; `require(perm)` returns an inner async `dependency`.
- Permissions are strings in `PERMISSIONS` in `app/core/rbac.py`. Roles: `admin, manager, developer, operator, viewer`. Perms: `user.manage, credential.write, content.write, job.request, job.run_check, job.approve, job.cancel, schedule.write, read`. Adding a permission means editing that dict — there is no other registry.
- DB access: `db: AsyncSession = Depends(get_db)` and SQLAlchemy 2.0 `select()` style — `(await db.execute(select(X).where(...))).scalar_one_or_none()`. Legacy `db.query()` is used only inside sync Celery tasks.
- Sync vs async split: FastAPI uses `AsyncSessionLocal` / `get_db` (asyncpg). Celery tasks are plain `def` and use `SyncSessionLocal` (psycopg2) with `try/finally: db.close()` — never `asyncio.run()` in a task. Both engines are in `app/db/session.py`.
- Celery tasks are registered with an explicit name: `@celery_app.task(name="run_job")`.
- Models: `class Base(DeclarativeBase)`, `Mapped[...]` + `mapped_column(...)`, `__tablename__` snake_case plural. Enums are `class X(str, enum.Enum)` (`InventoryFormat`, `CredentialKind`, `JobMode`, `JobStatus`). Models: `User, Role, Project, Inventory, Credential, Playbook, JobTemplate, JobRun, JobEvent, Schedule, Commit, AuditLog` + `user_roles` association table.
- Every mutating endpoint calls `await audit(db, "<action>", actor_user_id=..., object_type=..., object_id=..., detail=...)` from `app/services/audit.py`. Existing actions: `job_requested`, `job_approved`, `job_rejected`, `job_canceled`.
- Path traversal: any user-supplied relative path must go through `validate_safe_path(base_dir, rel_path)` in `app/services/content.py`; project roots come from `get_project_repo_path(project_name)`.
- Config: add settings as typed fields on `Settings` in `app/core/config.py` (pydantic-settings, env-var named identically). Derived URLs are `@property` (`DATABASE_URL`, `SYNC_DATABASE_URL`).
- Dependencies are exactly pinned (`==`) in `backend/pyproject.toml`. Keep it that way; no ranges.

Frontend:
- All HTTP goes through `apiFetch<T>(endpoint, options)` in `frontend/src/lib/api.ts`. It sets `credentials: "include"`, adds `Content-Type: application/json` for string bodies, adds `X-Requested-With: XMLHttpRequest` for POST/PUT/PATCH/DELETE, unwraps `detail.code`/`detail.message` into a thrown `ApiError`, and returns `{}` for 204. Never call `fetch` directly.
- TypeScript is strict: `strict`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `noEmit`, `jsx: react-jsx`, `moduleResolution: bundler`.
- Named export plus a `default` export for page components (`export function App() {}` / `export default App`); props and payloads typed with `interface`.
- Pinned exact versions in `package.json` (no `^`). React 18.3.1 and Tailwind 3.4.17 — do not use React 19 or Tailwind 4 APIs.

## Important Files

| Path | Why it matters |
| --- | --- |
| `compose.yaml` | Podman Compose topology, volume wiring, api self-wait loop. |
| `Containerfile.backend` | `python:3.12-slim-bookworm`; `uv` 0.5.24 installs into system site-packages in a builder stage; `uv` binary removed; runs as `USER runner`. |
| `Containerfile.web` | `node:22-alpine` build -> `nginx:alpine` runtime. |
| `nginx.conf` | Serves SPA and proxies `/api` to `api`. |
| `.env` | `env_file` for `api`/`worker`/`beat`. |
| `backend/app/main.py` | FastAPI app, startup seeding, generic exception handler. |
| `backend/app/core/config.py` | Settings, env var names, derived database URLs. |
| `backend/app/core/rbac.py` | Role/permission matrix. |
| `backend/app/db/models.py` | All SQLAlchemy models and enums. |
| `backend/app/tasks/run_job.py` | Git archive execution, credential materialization, event streaming, cleanup. |
| `backend/app/api/jobs.py` | Job request/approve/cancel/events HTTP flow. |
| `backend/tests/conftest.py` | Test DB, session, and ASGI client fixtures. |
| `frontend/src/lib/api.ts` | Required frontend HTTP wrapper and error handling. |
| `frontend/vite.config.ts` | Vite dev proxy to backend. |

Env var names: `POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, REDIS_URL, JWT_SECRET, FERNET_KEY, BOOTSTRAP_ADMIN_USER, BOOTSTRAP_ADMIN_PASSWORD, COOKIE_SECURE, CONTENT_ROOT, ARTIFACT_ROOT`.

Warning: `.env` is present in the working tree and `Settings` ships real-looking defaults for `JWT_SECRET`/`FERNET_KEY`/`POSTGRES_PASSWORD`/`BOOTSTRAP_ADMIN_PASSWORD`; never paste secret values into code, commits, logs, or chat, and override all of them before any non-local deployment.

## Runtime & Tooling Preferences

- Container runtime is Podman Compose — use `podman compose`, not `docker compose`.
- Backend Python >=3.12; images install with `uv pip install --system`, not pip/poetry. Host-side `uv pip install --system -e '.[dev]'` fails on Ubuntu's externally-managed Python — run backend work inside the container, or a dedicated venv.
- Frontend package manager is npm with committed `package-lock.json`; use `npm ci` (the web image does).
- Formatting/linting: none configured anywhere — no ruff, black, mypy, eslint, or prettier config exists. Match the style of the file you are editing; do not introduce a formatter or reflow unrelated code as part of a change.
- `ansible-lint==24.12.2` is a backend runtime dependency, used for playbook content, not for this repo's Python.

## Testing & QA

- pytest 8.3.4 + pytest-asyncio 0.25.3. Config in `backend/pyproject.toml`: `asyncio_mode = "auto"`, `asyncio_default_fixture_loop_scope = "session"`, `testpaths = ["tests"]`.
- `backend/tests/conftest.py` builds its own engine against database `ansible_webgui_test` on host `postgres` and provides: `setup_test_db` (session-scoped, autouse — `drop_all`/`create_all`, points `seed.AsyncSessionLocal` at the test sessionmaker and runs `seed_roles_and_admin()`, drops on teardown), `db` (function-scoped `AsyncSession`), and `client` (httpx `AsyncClient` over `ASGITransport(app=app)` with `app.dependency_overrides[get_db]` set and cleared).
- Required marker: async tests that touch the session-scoped fixtures must be decorated `@pytest.mark.asyncio(loop_scope="session")` — this pytest-asyncio version has no `asyncio_default_test_loop_scope` option, so omitting it produces cross-loop failures. Copy `backend/tests/test_approvals.py`.
- Tests need live Postgres reachable as hostname `postgres` and database `ansible_webgui_test` to exist. Run: `podman compose exec api pytest -q`. Existing files: `test_approvals.py`, `test_auth.py`, `test_rbac.py`; convention is `test_<area>.py` / `test_<behavior>_<expectation>`, building ORM rows directly against `db`, asserting via `pytest.raises(ValueError, match="<code>")` for service rules and via `client` for HTTP.
- No coverage config, no frontend test runner. Frontend QA is `npx tsc --noEmit` plus `npm run build`.
- Security QA is expected on dependency changes: `pip-audit` (backend) and `npm audit` (frontend).

## Tooling policy

- Use `xd://graphify_explain` with a single symbol name, or `xd://graphify_path` between two symbols, for relationship answers; `graphify_query` returns a flat node list and truncates at ~2000 tokens, so use it only to locate candidate files, then `read` them.
- Pass `context_filter=["call"]` and raise the budget when a query truncates.
- Graph regeneration is key-free (mounted `graphify_build` requires `DEEPSEEK_API_KEY` and fails): `graphify extract . --code-only && graphify cluster-only . --no-label`, run from the repo root; then `xd://graphify_update` after edits.
- Note that `graphify-out/` is gitignored, so a fresh checkout must run the extract command above before any graphify tool will answer.
- Any command whose output can exceed ~50 lines (`pytest`, `podman compose logs`, `npm run build`, `pip-audit`, `npm audit`, job stdout) uses `xd://mcp__context_mode_ctx_execute` or `xd://mcp__context_mode_ctx_batch_execute` instead of raw bash.
- Re-query large indexed docs and captured command output with `xd://mcp__context_mode_ctx_search` before re-reading raw files.
- Exact device paths: `xd://graphify_query`, `xd://graphify_update`, `xd://graphify_build`, `xd://mcp__context_mode_ctx_execute`, `xd://mcp__context_mode_ctx_batch_execute`, `xd://mcp__context_mode_ctx_execute_file`, `xd://mcp__context_mode_ctx_search`, `xd://mcp__context_mode_ctx_doctor`.

## Tooling & Skills Available to Assistants

- Skill `ansible-webgui-stack` — canonical service map, the four security invariants, and verification commands. Read before changing auth, approvals, credentials, or the job runner.
- Skill `graphify-no-key-fallback` — the mounted `graphify_build` tool fails with `backend 'deepseek' requires DEEPSEEK_API_KEY`. Build the graph key-free instead:
  ```sh
  graphify extract . --code-only && graphify cluster-only . --no-label
  ```
  Produces `graphify-out/graph.json`, `GRAPH_REPORT.md`, `graph.html`. Then use `graphify_query` / `graphify_explain` / `graphify_path` to trace call flow and blast radius before a refactor, and `graphify_update` after edits.
- context-mode MCP (`ctx_*`) — use `ctx_batch_execute` to run several scans in one call with output auto-indexed, `ctx_execute_file` for large files, and `ctx_search` to re-query anything already indexed. Prefer these over raw `cat`/`grep` when output would be long.
- Skill `context7-docs` (`resolve-library-id` -> `query-docs`) — version-accurate docs for FastAPI, SQLAlchemy 2.0, Celery/RedBeat, ansible-runner, react-query. Use it rather than recalling APIs, given the exact pins here.
- Persistent memory / skills (`memory_search`, `skill_manage`) — search project memory before repeating a debugging path; record durable repo conventions.

## Known Gaps

- The frontend is a scaffold: three source files, a hardcoded-default login form with inline styles. `react-router-dom`, `@tanstack/react-query`, `tailwindcss`, `@monaco-editor/react`, and `@xterm/xterm` are installed but not wired — there is no `tailwind.config.js`, no `postcss.config.js`, and no CSS file. Any UI work sets those up first.
- `backend/app/tasks/prune.py::prune_old_data()` is `pass` — an unimplemented stub, not a working retention job.
- `app/main.py` uses the deprecated `@app.on_event("startup")` and seeds roles/admin on every api boot.
- No CI, no linter, no frontend tests.
- Schedules use `RedBeatSchedulerEntry` keyed `redbeat:job:<name>` (`app/api/schedules.py`), stored on `Schedule.redbeat_key`.
- Alembic reads its URL from code — `env.py` overrides `sqlalchemy.url` with `settings.SYNC_DATABASE_URL` (sync psycopg2 engine, `NullPool`); the value in `alembic.ini` is ignored. Revision files are named `%(rev)s_%(slug)s`.
