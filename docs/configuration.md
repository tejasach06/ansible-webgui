# Configuration

This guide details all environment variables required by the Ansible WebGUI stack.

## Configuration Table

| Key | Default | Purpose | Must Change? |
| :--- | :--- | :--- | :--- |
| `POSTGRES_HOST` | `postgres` | PostgreSQL host | No |
| `POSTGRES_PORT` | `5432` | PostgreSQL port | No |
| `POSTGRES_DB` | `ansible_webgui` | PostgreSQL database name | No |
| `POSTGRES_USER` | `ansible` | PostgreSQL user | No |
| `POSTGRES_PASSWORD` | `change-me` | PostgreSQL password | **Yes** |
| `REDIS_URL` | `redis://redis:6379/0` | Redis broker and SSE pub/sub URL | No |
| `JWT_SECRET` | `change-me` | JWT signing secret | **Yes** |
| `FERNET_KEY` | `change-me` | Fernet key for credential encryption | **Yes** |
| `BOOTSTRAP_ADMIN_USER` | `admin` | Initial admin username | No |
| `BOOTSTRAP_ADMIN_PASSWORD` | `change-me` | Initial admin password | **Yes** |
| `COOKIE_SECURE` | `false` | Secure cookie flag (set `true` for TLS) | No (see Security) |
| `CONTENT_ROOT` | `/data/content` | Content root directory | No |
| `ARTIFACT_ROOT` | `/data/artifacts` | Runner artifact directory | No |

## Security Notes

*   **Must Change Keys**: The fields marked **Yes** must be generated and updated before exposing the stack. 
*   **Fernet Key Generation**: To generate a secure `FERNET_KEY`, run:
    ```sh
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```
*   **Hardening**: For information on securing the stack before production deployment, see the [Security documentation](SECURITY.md).
*   **Postgres Defaults**: Note that the `compose.yaml` file provides internal default credentials (`ansible_webgui` / `ansible` / `ansible_secret`). These will be used if the `.env` file is missing. For secure environments, ensure your `.env` overrides these with your own credentials.
*   **Cookie Security**: `COOKIE_SECURE` should be set to `true` when running behind a TLS-terminated proxy or load balancer.
