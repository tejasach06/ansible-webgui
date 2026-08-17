import enum
from datetime import datetime
from typing import Optional, List
from app.core.time import utcnow
from sqlalchemy import (
    String, Integer, SmallInteger, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint, Table, Column, Text, LargeBinary, Index, func
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

class NotificationKind(str, enum.Enum):
    webhook = "webhook"
    slack = "slack"

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

class ProjectRole(str, enum.Enum):
    owner = "owner"
    maintainer = "maintainer"
    developer = "developer"
    operator = "operator"
    viewer = "viewer"

class HostResultStatus(str, enum.Enum):
    ok = "ok"
    changed = "changed"
    failed = "failed"
    unreachable = "unreachable"
    skipped = "skipped"

class PipelineStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    queued = "queued"
    running = "running"
    successful = "successful"
    failed = "failed"
    canceled = "canceled"

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

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
    default_inventory_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("inventories.id", name="fk_projects_default_inventory", ondelete="SET NULL", use_alter=True), nullable=True)
class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id"), Index("ix_project_memberships_user_id", "user_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class Inventory(Base):
    __tablename__ = "inventories"
    __table_args__ = (
        Index("uq_inventories_scope_name", func.coalesce(Column("project_id"), 0), "name", unique=True),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    rel_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    format: Mapped[InventoryFormat] = mapped_column(Enum(InventoryFormat), nullable=False)
class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[CredentialKind] = mapped_column(Enum(CredentialKind), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    become_same_as_ssh: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    public_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
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
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    playbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("playbooks.id"), nullable=False)
    inventory_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("inventories.id"), nullable=True)
    limit_pattern: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    skip_tags: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extra_vars: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    verbosity: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    forks: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False)
    credential_ids: Mapped[List[int]] = mapped_column(ARRAY(Integer), default=list, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    survey_spec: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    diff_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_limit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_tags: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_skip_tags: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_extra_vars: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_verbosity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_diff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_credentials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_inventory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class Pipeline(Base):
    __tablename__ = "pipelines"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class PipelineStep(Base):
    __tablename__ = "pipeline_steps"
    __table_args__ = (UniqueConstraint("pipeline_id", "position"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(Integer, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_templates.id", ondelete="RESTRICT"), nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    continue_on_failure: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pipelines.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[PipelineStatus] = mapped_column(Enum(PipelineStatus), default=PipelineStatus.queued, nullable=False)
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    current_position: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    params_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_templates.id", ondelete="SET NULL"), nullable=True)
    playbook_id: Mapped[int] = mapped_column(Integer, ForeignKey("playbooks.id"), nullable=False)
    inventory_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("inventories.id", ondelete="SET NULL"), nullable=True)
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    pipeline_step_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pipeline_steps.id", ondelete="SET NULL"), nullable=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    survey_secrets_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    relaunch_of_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True)

class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (UniqueConstraint("job_run_id", "counter"), Index("ix_job_events_run_event", "job_run_id", "event"),)
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False)
    counter: Mapped[int] = mapped_column(Integer, nullable=False)
    uuid: Mapped[str] = mapped_column(String, nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)
    host: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    task: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class JobPlay(Base):
    __tablename__ = "job_plays"
    __table_args__ = (UniqueConstraint("job_run_id", "uuid"),)
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False)
    uuid: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    counter: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class JobTask(Base):
    __tablename__ = "job_tasks"
    __table_args__ = (UniqueConstraint("job_run_id", "uuid"), Index("ix_job_tasks_job_run_id", "job_run_id"),)
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False)
    play_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("job_plays.id", ondelete="CASCADE"), nullable=False)
    uuid: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    counter: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class JobHostResult(Base):
    __tablename__ = "job_host_results"
    __table_args__ = (Index("ix_job_host_results_job_run_host", "job_run_id", "host"),)
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("job_tasks.id", ondelete="CASCADE"), nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[HostResultStatus] = mapped_column(Enum(HostResultStatus), nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    counter: Mapped[int] = mapped_column(Integer, nullable=False)
    ignore_errors: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    res: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_templates.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    cron_expr: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, default="UTC", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    redbeat_key: Mapped[str] = mapped_column(String, nullable=False)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_job_run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_runs.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    kind: Mapped[NotificationKind] = mapped_column(Enum(NotificationKind), nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    on_success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    on_failure: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    on_approval_needed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

class Commit(Base):
    __tablename__ = "commits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    sha: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    author_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    files_changed: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    object_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    object_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
