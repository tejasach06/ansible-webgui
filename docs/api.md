# API

Base URL is the deployment origin. Application routes use the `/api` prefix. Interactive docs are at `/api/docs`; OpenAPI schema is at `/api/openapi.json`.

## Auth

Login sets HttpOnly cookies. Browser clients and `curl` examples must send cookies on subsequent requests; frontend `apiFetch` uses `credentials: include`. Every mutating request needs `X-Requested-With: XMLHttpRequest` or FastAPI returns 403 `csrf_missing`. Refresh with `POST /api/auth/refresh`. `GET /api/me` returns assigned roles and effective permissions.

## Error envelope

Errors use:

```json
{"detail": {"code": "...", "message": "..."}}
```

| Code | Status |
| --- | --- |
| `invalid_credentials` | 401 |
| `csrf_missing` | 403 |
| `forbidden` | 403 |
| `playbook_not_found` | 404 |
| `inventory_not_found` | 404 |
| `job_not_found` | 404 |
| `template_busy` | 409 |
| `self_approval_forbidden` | 400/409 |
| `bad_state` | 400/409 |
| `internal_error` | 500 |

## Auth

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/auth/login` | `public + CSRF` | Sets access and refresh HttpOnly cookies. |
| `POST` | `/api/auth/refresh` | `public` | Refresh cookie issues a new access token. |
| `POST` | `/api/auth/logout` | `public + CSRF` | Clears auth cookies. |
| `GET` | `/api/me` | `authenticated` | Returns roles and effective perms. |
## Health

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/health` | `public` | Returns service health. |
## Users

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/users` | `user.manage` | List users. |
| `POST` | `/api/users` | `user.manage` | Create user. |
| `PATCH` | `/api/users/{user_id}` | `user.manage` | Update username, active flag, or roles. |
| `POST` | `/api/users/{user_id}/password` | `user.manage` | Set password. |
| `DELETE` | `/api/users/{user_id}` | `user.manage` | Delete user. |
## Credentials

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/credentials` | `read` | List credentials. |
| `POST` | `/api/credentials` | `credential.write` | Create encrypted credential. |
| `DELETE` | `/api/credentials/{cred_id}` | `credential.write` | Delete credential. |
## Projects

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/projects` | `read` | List projects. |
| `POST` | `/api/projects` | `content.write` | Create/register project. |
| `DELETE` | `/api/projects/{project_id}` | `content.write` | Delete project. |
## Playbooks

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/playbooks` | `read` | List playbooks. |
| `POST` | `/api/playbooks` | `content.write` | Register playbook. |
| `DELETE` | `/api/playbooks/{playbook_id}` | `content.write` | Delete playbook row. |
## Inventories

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/inventories` | `read` | List inventories. |
| `POST` | `/api/inventories` | `content.write` | Register inventory. |
| `DELETE` | `/api/inventories/{inventory_id}` | `content.write` | Delete inventory row. |
| `GET` | `/api/inventories/{inventory_id}/file` | `read` | Read inventory file content + repo sha. |
| `POST` | `/api/inventories/{inventory_id}/file` | `content.write` | Commit inventory file edit; 409 on stale `base_sha`. |
| `PATCH` | `/api/inventories/{inventory_id}` | `content.write` | Rename inventory / change format. |
## Job templates

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/job_templates` | `read` | List templates. |
| `POST` | `/api/job_templates` | `schedule.write` | Create template. |
| `PATCH` | `/api/job_templates/{template_id}` | `schedule.write` | Update template. |
| `DELETE` | `/api/job_templates/{template_id}` | `schedule.write` | Delete template. |
## Jobs

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/jobs` | `read` | List jobs. |
| `POST` | `/api/jobs` | `job.request` | Request check/live job. |
| `GET` | `/api/jobs/{job_id}` | `read` | Job detail. |
| `POST` | `/api/jobs/{job_id}/approve` | `job.approve` | Approve and enqueue. |
| `POST` | `/api/jobs/{job_id}/reject` | `job.approve` | Reject pending job. |
| `POST` | `/api/jobs/{job_id}/cancel` | `job.cancel` | Cancel running or queued job. |
| `GET` | `/api/jobs/{job_id}/events/stream` | `authenticated` | SSE stream with replay by counter. |
## Schedules

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/schedules` | `read` | List schedules. |
| `POST` | `/api/schedules` | `schedule.write` | Create RedBeat schedule. |
| `PATCH` | `/api/schedules/{schedule_id}` | `schedule.write` | Update schedule. |
| `DELETE` | `/api/schedules/{schedule_id}` | `schedule.write` | Delete schedule. |
## Content

| Method | Path | Required permission | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/content/{project_id}/file` | `read` | Read file content. |
| `POST` | `/api/content/{project_id}/save` | `content.write` | Save file. |
| `GET` | `/api/content/{project_id}/history` | `read` | Commit history. |
| `GET` | `/api/content/{project_id}/diff` | `read` | Diff content. |
| `POST` | `/api/content/{project_id}/revert` | `content.write` | Revert commit. |
| `POST` | `/api/content/{project_id}/roles` | `content.write` | Create role content. |

## Worked example: login, request, approve

```sh
curl -c cookies.txt -b cookies.txt \
  -H 'Content-Type: application/json' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -d '{"username":"admin","password":"change-me"}' \
  http://localhost:8000/api/auth/login

curl -c cookies.txt -b cookies.txt \
  -H 'Content-Type: application/json' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -d '{"playbook_id":1,"inventory_id":1,"mode":"live","credential_ids":[]}' \
  http://localhost:8000/api/jobs

curl -c cookies.txt -b cookies.txt \
  -H 'Content-Type: application/json' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -d '{"approval_note":"approved"}' \
  http://localhost:8000/api/jobs/1/approve
```

Two-person approval means the approver must differ from the requester.

## Worked example: stream events

```sh
curl -N -b cookies.txt 'http://localhost:8000/api/jobs/1/events/stream?after_counter=0'
```

Sample frames:

```text
data: {"counter":1,"stdout":"TASK [ping]","event":"runner_on_start"}

: heartbeat
```

## Pagination

List endpoints clamp `limit` to 200.

This file is hand-maintained; `/api/openapi.json` is authoritative for request and response shapes because routers do not declare `response_model`.
