import enum
from datetime import datetime
from typing import Optional, List, Any
from sqlalchemy import (
    String, Integer, SmallInteger, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, Table, Column, Text, LargeBinary
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, BIGINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class InventoryFormat(str, enum.Enum):
    yaml = "yaml"
    ini = "ini"

class CredentialKind(str, enum.Enum):
    ssh_key = "ssh_key"
    ssh_password = "ssh_password"
    vault_password = "vault_password"
    become_password = "become_password"

class JobMode(str, enum.Enum):
    check = "check"
    live = "live"

class JobStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    queued = "queued"
    running = "running"
    successful = "successful"
    failed = "failed"
    canceled = "canceled"
    timed_out = "timed_out"

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    roles: Mapped[List["Role"]] = relationship("Role", secondary=user_roles, lazy="joined")

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    git_path: Mapped[str] = mapped_column(String, nullable=False)
    default_branch: Mapped[str] = mapped_column(String, default="main", nullable=False)

class Inventory(Base):
    __tablename__ = "inventories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    rel_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    format: Mapped[InventoryFormat] = mapped_column(Enum(InventoryFormat), nullable=False)

class Credential(Base):
    __tablename__ = "credentials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    kind: Mapped[CredentialKind] = mapped_column(Enum(CredentialKind), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    payload_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

class Playbook(Base):
    __tablename__ = "playbooks"
    __table_args__ = (UniqueConstraint("project_id", "rel_path"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    rel_path: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

class JobTemplate(Base):
    __tablename__ = "job_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    playbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("playbooks.id"), nullable=False)
    inventory_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventories.id"), nullable=False)
    limit_pattern: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    skip_tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extra_vars: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    verbosity: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    forks: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False)
    credential_ids: Mapped[List[int]] = mapped_column(ARRAY(Integer), default=list, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_templates.id", ondelete="SET NULL"), nullable=True)
    playbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("playbooks.id"), nullable=False)
    inventory_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("inventories.id", ondelete="SET NULL"), nullable=True)
    mode: Mapped[JobMode] = mapped_column(Enum(JobMode), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.pending_approval, nullable=False)
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    approval_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    artifact_dir: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stats: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    params_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (UniqueConstraint("job_run_id", "counter"),)
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False)
    counter: Mapped[int] = mapped_column(Integer, nullable=False)
    uuid: Mapped[str] = mapped_column(String, nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)
    host: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    task: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_templates.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    cron_expr: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, default="UTC", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    redbeat_key: Mapped[str] = mapped_column(String, nullable=False)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_job_run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

class Commit(Base):
    __tablename__ = "commits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    sha: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    author_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    files_changed: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    object_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    object_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
