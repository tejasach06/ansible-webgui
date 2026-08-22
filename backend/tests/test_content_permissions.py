from uuid import uuid4

import pytest
from sqlalchemy import select
from test_content_api import login

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import Project, ProjectMembership, ProjectRole, Role, User
from app.services.content import init_project_repo

MUTATE = {"X-Requested-With": "XMLHttpRequest"}


@pytest.mark.asyncio(loop_scope="session")
async def test_content_permissions_and_path_validation(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CONTENT_ROOT", str(tmp_path))

    # Create project
    p_name = f"perm-proj-{uuid4().hex[:8]}"
    project = Project(name=p_name, git_path=str(tmp_path / p_name), default_branch="main")
    db.add(project)
    await db.commit()
    await init_project_repo(db, project, "admin", "admin@example.com")

    # Admin can create role (200, not 403)
    await login(client, username="admin")
    role_res = await client.post(
        f"/api/content/{project.id}/roles",
        json={"role_name": "webserver"},
        headers=MUTATE,
    )
    assert role_res.status_code == 200
    assert role_res.json()["status"] == "ok"

    # Create viewer user
    user_role = (await db.execute(select(Role).where(Role.name == "user"))).scalar_one()
    viewer_user = User(
        username=f"viewer-{uuid4().hex[:6]}",
        email="viewer@example.com",
        password_hash=hash_password("changeme"),
        is_active=True,
        roles=[user_role],
    )
    db.add(viewer_user)
    await db.commit()

    # Assign viewer project membership
    membership = ProjectMembership(project_id=project.id, user_id=viewer_user.id, role=ProjectRole.viewer)
    db.add(membership)
    await db.commit()

    # Viewer gets 403 from create_role
    await login(client, username=viewer_user.username, password="changeme")
    viewer_role_res = await client.post(
        f"/api/content/{project.id}/roles",
        json={"role_name": "dbserver"},
        headers=MUTATE,
    )
    assert viewer_role_res.status_code == 403
    assert viewer_role_res.json()["detail"]["code"] == "forbidden"

    # Revert with path traversal rel_path returns 400 bad_path
    await login(client, username="admin")
    revert_bad_path = await client.post(
        f"/api/content/{project.id}/revert",
        json={"sha": role_res.json()["sha"], "rel_path": "../etc/passwd"},
        headers=MUTATE,
    )
    assert revert_bad_path.status_code == 400
    assert revert_bad_path.json()["detail"]["code"] == "bad_path"
