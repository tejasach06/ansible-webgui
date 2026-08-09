# Ansible WebGUI

Self-hosted web UI for running Ansible playbooks: git-backed content editing, RBAC,
approval-gated job runs, live log streaming, scheduling, and an audit trail.

Stack: FastAPI + Celery + PostgreSQL + Redis, React 18 + Vite, served behind nginx.

## Quickstart

```bash
cp .env.example .env      # then set SECRET_KEY, FERNET_KEY, POSTGRES_PASSWORD
podman compose up -d --build
```

UI: http://localhost:8080 — API docs: http://localhost:8000/api/docs

## Branches

- `main` — runtime tree only (application source + container/compose files).
- `dev` — full development tree: tests, `docs/`, contributor and agent guides.

## License

See [LICENSE](LICENSE).
