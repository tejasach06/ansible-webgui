from typing import Optional, List

from pydantic import BaseModel

from app.db.models import JobMode


class JobRequest(BaseModel):
    template_id: Optional[int] = None
    playbook_id: int
    inventory_id: int
    mode: JobMode = JobMode.live
    limit: Optional[str] = None
    tags: Optional[str] = None
    skip_tags: Optional[str] = None
    extra_vars: dict = {}
    verbosity: int = 0
    forks: int = 5
    become: bool = False
    become_user: Optional[str] = None
    become_method: Optional[str] = None
    credential_ids: List[int] = []


class ApproveRequest(BaseModel):
    approval_note: Optional[str] = None
