import pytest
from app.core.rbac import PERMISSIONS, get_user_permissions

def test_rbac_matrix():
    assert "user.manage" in PERMISSIONS["admin"]
    assert "user.manage" not in PERMISSIONS["manager"]
    assert "content.write" in PERMISSIONS["developer"]
    assert "job.approve" in PERMISSIONS["manager"]
    assert "job.approve" not in PERMISSIONS["developer"]
    assert "read" in PERMISSIONS["viewer"]
    assert len(PERMISSIONS["viewer"]) == 1
