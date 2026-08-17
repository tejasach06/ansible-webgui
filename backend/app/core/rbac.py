from typing import Dict, Set

GLOBAL_PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {"system.admin", "user.manage", "notification.write", "project.create", "read"},
    "user": {"project.create", "read"},
    "auditor": {"audit.read", "read"},
}

PROJECT_PERMISSIONS: Dict[str, Set[str]] = {
    "owner":      {"project.admin", "credential.write", "content.write", "job.request", "job.run_check", "job.approve", "job.cancel", "schedule.write", "pipeline.write", "read"},
    "maintainer": {"credential.write", "content.write", "job.request", "job.run_check", "job.approve", "job.cancel", "schedule.write", "pipeline.write", "read"},
    "developer":  {"content.write", "job.request", "job.run_check", "read"},
    "operator":   {"job.request", "job.run_check", "job.cancel", "read"},
    "viewer":     {"read"},
}

def get_user_permissions(roles: list) -> Set[str]:
    perms = set()
    for role in roles:
        role_name = role.name if hasattr(role, "name") else str(role)
        perms.update(GLOBAL_PERMISSIONS.get(role_name, set()))
    return perms

def get_project_permissions(role_name: str) -> Set[str]:
    return PROJECT_PERMISSIONS.get(role_name, set())
