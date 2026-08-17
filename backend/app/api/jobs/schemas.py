from typing import Literal, Optional, List

from pydantic import BaseModel

from app.db.models import JobMode


class JobRequest(BaseModel):
    template_id: Optional[int] = None
    playbook_id: Optional[int] = None
    inventory_id: Optional[int] = None
    mode: Optional[JobMode] = None
    limit: Optional[str] = None
    tags: Optional[str] = None
    skip_tags: Optional[str] = None
    extra_vars: Optional[dict] = None
    survey_answers: dict = {}
    verbosity: Optional[int] = None
    forks: Optional[int] = None
    become: Optional[bool] = None
    become_user: Optional[str] = None
    become_method: Optional[str] = None
    diff: Optional[bool] = None
    credential_ids: Optional[List[int]] = None

class ApproveRequest(BaseModel):
    approval_note: Optional[str] = None

class RelaunchRequest(BaseModel):
    hosts: Literal["all", "failed"] = "all"
    mode: Optional[JobMode] = None
