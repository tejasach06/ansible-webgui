# Contributing Guide

## Branches

The project follows a split-branch convention:
- **`main`**: Carries the minimal runtime tree.
- **`dev`**: Carries the full development tree, documentation, and contributor guides.

All contributions should target the **`dev`** branch.

## Local Development Setup

1. Copy the example environment file:
   ```sh
   cp .env.example .env
   ```
2. Edit `.env` and update the following required keys:
   - `POSTGRES_PASSWORD`
   - `JWT_SECRET`
   - `FERNET_KEY`
   - `BOOTSTRAP_ADMIN_PASSWORD`
3. Start the stack using Podman:
   ```sh
   podman compose up -d --build
   ```

## Development Checks

### Backend Checks
- **Run tests**:
  ```sh
  podman compose exec api pytest -q
  ```
- **Full-suite alternative**:
  ```sh
  podman compose --profile test run --rm tests
  ```
- **Lint**:
  ```sh
  ruff check backend
  ```
  Note: `filterwarnings = ["error"]` in `backend/pyproject.toml` ensures that any new warnings result in test failure.

### Frontend Checks
- **From the `frontend/` directory**:
  ```sh
  npm run typecheck
  npm run build
  ```

## Codebase Conventions

- **Linting**: Ruff is configured with a line length of 120 and the following enabled rules: `E,F,I,UP,B,SIM,RET,C4,ARG`.
- **Backend Architecture**: Routers should remain thin, with business logic encapsulated in `app/services/`.
- **Error Handling**: Services should raise bare `ValueError` exceptions, which the router translates into the `{"detail": {"code", "message"}}` envelope.
- **Security & RBAC**:
  - Enforce RBAC using `Depends(require(perm))` or `assert_project_perm()`.
  - Mutating endpoints MUST call `audit()` (`app/services/audit.py`).
- **Frontend**: API calls must use `apiFetch<T>()` from `src/lib/api.ts` to ensure consistent data handling.

## Commit Style

Please follow the existing conventional commit style: `type(scope): summary` (e.g., `feat(ui):`, `fix(worker):`, `refactor(db):`, `chore:`).
