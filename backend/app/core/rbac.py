from typing import Dict, Set

PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {
        "user.manage",
        "credential.write",
        "content.write",
        "job.request",
        "job.run_check",
        "job.approve",
        "job.cancel",
        "schedule.write",
        "read",
    },
    "manager": {
        "job.request",
        "job.run_check",
        "job.approve",
        "job.cancel",
        "schedule.write",
        "read",
    },
    "developer": {
        "content.write",
        "job.request",
        "job.run_check",
        "read",
    },
    "operator": {
        "job.request",
        "job.run_check",
        "job.cancel",
        "read",
    },
    "viewer": {
        "read",
    },
}

def get_user_permissions(roles: list) -> Set[str]:
    perms = set()
    for role in roles:
        role_name = role.name if hasattr(role, "name") else str(role)
        perms.update(PERMISSIONS.get(role_name, set()))
    return perms
