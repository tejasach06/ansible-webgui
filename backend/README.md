# Ansible WebGUI Backend

FastAPI and Celery package for Ansible WebGUI.

Layout:

- `app/api/` — REST and SSE routers.
- `app/core/` — settings, auth, security, RBAC.
- `app/db/` — SQLAlchemy models, sessions, seed data.
- `app/services/` — business rules and reusable domain logic.
- `app/tasks/` — Celery worker, job runner, prune task.

Run backend tests from the stack:

```sh
podman compose exec api pytest -q
```

Apply or create migrations:

```sh
podman compose exec api alembic upgrade head
podman compose exec api alembic revision --autogenerate -m "add x"
```

Top-level docs: [README](../README.md), [architecture](../docs/architecture.md), and [contributing](../CONTRIBUTING.md).
