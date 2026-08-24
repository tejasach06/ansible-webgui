# Ansible WebGUI

Self-hosted web UI for running Ansible playbooks: git-backed content editing, RBAC,
approval-gated job runs, live log streaming, scheduling, and an audit trail.

Stack: FastAPI + Celery + PostgreSQL + Redis, React 18 + Vite (API serves the built frontend on a single port).

## Quickstart

```bash
cp .env.example .env      # then set JWT_SECRET, FERNET_KEY, POSTGRES_PASSWORD
podman compose up -d --build
podman compose --profile test run --rm tests
```

UI: http://127.0.0.1:8080 — API docs: http://127.0.0.1:8080/api/docs (configurable via WEBGUI_HOST and WEBGUI_PORT)

## Documentation

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Backend](backend/README.md)
- [Frontend](frontend/README.md)

## Branches

- `main` — runtime tree only (application source + container/compose files).
- `dev` — full development tree: tests, `docs/`, contributor and agent guides.

## License

See [LICENSE](LICENSE).
