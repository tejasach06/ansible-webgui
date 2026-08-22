# Ansible WebGUI

Self-hosted web UI for running Ansible playbooks: git-backed content editing, RBAC,
approval-gated job runs, live log streaming, scheduling, and an audit trail.

Stack: FastAPI + Celery + PostgreSQL + Redis, React 18 + Vite, served behind nginx.

## Quickstart

```bash
cp .env.example .env      # then set JWT_SECRET, FERNET_KEY, POSTGRES_PASSWORD
podman compose up -d --build
podman compose --profile test run --rm tests
```

UI: http://localhost:8080 — API docs: http://localhost:8000/api/docs

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
