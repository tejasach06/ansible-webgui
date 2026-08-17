import pytest
from app.core.rbac import GLOBAL_PERMISSIONS, PROJECT_PERMISSIONS, get_user_permissions, get_project_permissions

def test_rbac_matrix():
    assert "user.manage" in GLOBAL_PERMISSIONS["admin"]
    assert "project.create" in GLOBAL_PERMISSIONS["user"]
    assert "audit.read" in GLOBAL_PERMISSIONS["auditor"]

    assert "project.admin" in PROJECT_PERMISSIONS["owner"]
    assert "credential.write" in PROJECT_PERMISSIONS["maintainer"]
    assert "content.write" in PROJECT_PERMISSIONS["developer"]
    assert "job.request" in PROJECT_PERMISSIONS["operator"]
    assert "read" in PROJECT_PERMISSIONS["viewer"]
    assert len(PROJECT_PERMISSIONS["viewer"]) == 1
