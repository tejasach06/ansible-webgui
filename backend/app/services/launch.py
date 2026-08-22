from typing import Any

from app.api.jobs.schemas import JobRequest
from app.db.models import JobMode, JobTemplate

ASKABLE = {
    "limit": "ask_limit",
    "tags": "ask_tags",
    "skip_tags": "ask_skip_tags",
    "extra_vars": "ask_extra_vars",
    "verbosity": "ask_verbosity",
    "diff": "ask_diff",
    "credential_ids": "ask_credentials",
    "inventory_id": "ask_inventory",
    "mode": "ask_mode",
}

def resolve_launch(template: JobTemplate | None, req: JobRequest, survey_vars: set[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    if template is None:
        effective = {
            "playbook_id": req.playbook_id,
            "inventory_id": req.inventory_id,
            "mode": req.mode or JobMode.live,
            "limit": req.limit,
            "tags": req.tags,
            "skip_tags": req.skip_tags,
            "extra_vars": req.extra_vars or {},
            "verbosity": req.verbosity if req.verbosity is not None else 0,
            "forks": req.forks if req.forks is not None else 5,
            "become": req.become if req.become is not None else False,
            "become_user": req.become_user,
            "become_method": req.become_method,
            "diff": req.diff if req.diff is not None else False,
            "credential_ids": req.credential_ids or [],
        }
        return effective, {}

    effective: dict[str, Any] = {}
    overrides: dict[str, Any] = {}
    unallowed: list = []

    # Simple scalar field checks
    scalar_fields = [
        ("limit", req.limit, getattr(template, "limit_pattern", None)),
        ("tags", req.tags, getattr(template, "tags", None)),
        ("skip_tags", req.skip_tags, getattr(template, "skip_tags", None)),
        ("verbosity", req.verbosity, getattr(template, "verbosity", 0)),
        ("diff", req.diff, getattr(template, "diff_mode", False)),
        ("inventory_id", req.inventory_id, getattr(template, "inventory_id", None)),
    ]

    for field, req_val, tpl_val in scalar_fields:
        if req_val is None:
            effective[field] = tpl_val
        elif req_val == tpl_val:
            effective[field] = req_val
        else:
            ask_flag = ASKABLE[field]
            if not getattr(template, ask_flag, False):
                unallowed.append(field)
            else:
                overrides[field] = {"template": tpl_val, "request": req_val}
            effective[field] = req_val

    # Mode check
    if req.mode is None:
        effective["mode"] = JobMode.live
    else:
        if req.mode != JobMode.live:
            if not getattr(template, "ask_mode", False):
                unallowed.append("mode")
            else:
                overrides["mode"] = {"template": "live", "request": req.mode.value if hasattr(req.mode, "value") else str(req.mode)}
        effective["mode"] = req.mode

    # Credential IDs set comparison
    tpl_creds = set(template.credential_ids or [])
    req_creds = set(req.credential_ids) if req.credential_ids is not None else None
    if req_creds is None:
        effective["credential_ids"] = list(tpl_creds)
    elif req_creds == tpl_creds:
        effective["credential_ids"] = list(req_creds)
    else:
        if not getattr(template, "ask_credentials", False):
            unallowed.append("credential_ids")
        else:
            overrides["credential_ids"] = {"template": sorted(tpl_creds), "request": sorted(req_creds)}
        effective["credential_ids"] = list(req_creds)

    # Extra vars comparison (keys produced by survey do not count)
    req_vars = req.extra_vars or {}
    tpl_vars = template.extra_vars or {}
    diff_vars = {k: v for k, v in req_vars.items() if k not in survey_vars and tpl_vars.get(k) != v}
    if diff_vars:
        if not getattr(template, "ask_extra_vars", False):
            unallowed.append("extra_vars")
        else:
            overrides["extra_vars"] = {
                "template": {k: tpl_vars.get(k) for k in diff_vars},
                "request": diff_vars,
            }

    merged_extra_vars = dict(tpl_vars)
    merged_extra_vars.update(req_vars)
    effective["extra_vars"] = merged_extra_vars

    # Other inherited defaults
    effective["playbook_id"] = req.playbook_id or template.playbook_id
    effective["forks"] = req.forks if req.forks is not None else getattr(template, "forks", 5)
    effective["become"] = req.become or False
    effective["become_user"] = req.become_user
    effective["become_method"] = req.become_method

    if unallowed:
        raise ValueError(f"override_not_allowed:{','.join(sorted(unallowed))}")

    return effective, overrides
