# Deployment

## Requirements

- Podman 4 or newer with `podman compose`.
- About 2 GB RAM.
- Port 8080 for the UI, and port 8000 only if the API must be reached directly.

## First deploy

```sh
git clone <repo-url> ansible-webgui
cd ansible-webgui
cp .env.example .env
# edit .env: set JWT_SECRET, FERNET_KEY, POSTGRES_PASSWORD, BOOTSTRAP_ADMIN_PASSWORD, COOKIE_SECURE=true
podman compose up -d --build
curl -fsS http://localhost:8000/api/health
```

Expected health response:

```json
{"status":"ok"}
```

Log in at `http://localhost:8080`, then rotate the admin password.

## Migrations

The `api` command applies migrations on every start with `alembic upgrade head`.

Manual commands:

```sh
podman compose exec api alembic upgrade head
podman compose exec api alembic revision --autogenerate -m "add x"
```

## Operations

```sh
podman compose logs -f api worker
podman compose ps
podman compose restart worker
```

Scale per-worker concurrency by changing `-c` in the `worker` command.

## Backup and restore

Back up Postgres and content repos:

```sh
podman compose exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > ansible-webgui.sql
```

The `content` volume holds the playbook git repositories and is source of truth. `artifacts` is disposable.

## Upgrades

```sh
podman compose pull
podman compose up -d --build
```

Migrations run at `api` boot.

## Teardown

```sh
podman compose down
podman compose down -v
```

`-v` destroys `pgdata`, `content`, `artifacts`, and `sshdata`. Treat it as destructive because `content` holds playbook git repositories.

## TLS and reverse proxy

Put a TLS terminator in front of `web` and set `COOKIE_SECURE=true`. Do not expose `8000` publicly; publish only `web` unless direct API access is required.
