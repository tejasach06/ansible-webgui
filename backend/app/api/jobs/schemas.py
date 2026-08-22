from typing import Literal

from pydantic import BaseModel

from app.db.models import JobMode


class JobRequest(BaseModel):
    template_id: int | None = None
    playbook_id: int | None = None
    inventory_id: int | None = None
    mode: JobMode | None = None
    limit: str | None = None
    tags: str | None = None
    skip_tags: str | None = None
    extra_vars: dict | None = None
    survey_answers: dict = {}
    verbosity: int | None = None
    forks: int | None = None
    become: bool | None = None
    become_user: str | None = None
    become_method: str | None = None
    diff: bool | None = None
    credential_ids: list[int] | None = None

class ApproveRequest(BaseModel):
    approval_note: str | None = None

class RelaunchRequest(BaseModel):
    hosts: Literal["all", "failed"] = "all"
    mode: JobMode | None = None
