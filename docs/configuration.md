# Configuration

| Name | Type | Default | Used by | Notes |
| --- | --- | --- | --- | --- |
| `POSTGRES_HOST` | `str` | `postgres` | api, worker, beat, api wait loop | Database host. |
| `POSTGRES_PORT` | `int` | `5432` | api, worker, beat | Database port. |
| `POSTGRES_DB` | `str` | `ansible_webgui` | postgres, api, worker, beat, api wait loop | Must match compose interpolation. |
| `POSTGRES_USER` | `str` | `ansible` | postgres, api, worker, beat, api wait loop | Must match compose interpolation. |
| `POSTGRES_PASSWORD` | `str` | `change-me` | postgres, api, worker, beat | Secret; override before use. |
| `REDIS_URL` | `str` | `redis://redis:6379/0` | api, worker, beat | Celery broker and SSE pub/sub. |
| `JWT_SECRET` | `str` | `change-me` | api | JWT signing secret. |
| `FERNET_KEY` | `str` | `change-me` | api, worker | Credential encryption key. |
| `BOOTSTRAP_ADMIN_USER` | `str` | `admin` | api startup seed | Initial admin username. |
| `BOOTSTRAP_ADMIN_PASSWORD` | `str` | `change-me` | api startup seed | Initial admin password; rotate after login. |
| `COOKIE_SECURE` | `bool` | `false` | api auth | Set `true` behind HTTPS. |
| `CONTENT_ROOT` | `str` | `/data/content` | api, worker, beat | Git content root. |
| `ARTIFACT_ROOT` | `str` | `/data/artifacts` | worker, api | Runner artifact and temp root. |

## Loading

`pydantic-settings` reads process environment into `Settings`. Compose passes `.env` through `env_file` to `api`, `worker`, and `beat`; `web` receives none.

## Derived database URLs

`DATABASE_URL` and `SYNC_DATABASE_URL` are computed `@property` values, not environment variables. Adding `DATABASE_URL` to `.env` will not change database connectivity.

## Secret generation

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Compose-only coupling

`POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` are also interpolated in `compose.yaml` for the `postgres` service and the `api` `pg_isready` loop. Keep them aligned with backend settings.

## Alembic

`backend/alembic/env.py` overrides `sqlalchemy.url` with `settings.SYNC_DATABASE_URL`; `alembic.ini` is ignored for runtime connection selection.
