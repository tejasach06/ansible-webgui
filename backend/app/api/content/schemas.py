from typing import Optional

from pydantic import BaseModel


class SaveFileRequest(BaseModel):
    rel_path: str
    content: str
    message: str
    base_sha: Optional[str] = None


class CreateRoleRequest(BaseModel):
    role_name: str


class RevertRequest(BaseModel):
    sha: str
    rel_path: str
