RESULTS = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0}
RUNNER_EVENTS = {"runner_on_ok", "runner_on_failed", "runner_on_unreachable", "runner_on_skipped"}
RELEVANT_EVENTS = (
    "playbook_on_play_start",
    "playbook_on_task_start",
    "runner_on_ok",
    "runner_on_failed",
    "runner_on_unreachable",
    "runner_on_skipped",
)


def _event_data(payload):
    return (payload or {}).get("event_data") or {}


def _host(host, data):
    return host or data.get("host")


def build_task_tree(rows) -> dict:
    plays = []
    current_play = None
    current_task = None
    tasks_by_uuid = {}
    for counter, event, host, payload in rows:
        if event.startswith("runner_item_on_"):
            continue
        data = _event_data(payload)
        if event == "playbook_on_play_start":
            current_play = {"uuid": data.get("play_uuid"), "name": data.get("play"), "counter": counter, "tasks": []}
            plays.append(current_play)
        elif event == "playbook_on_task_start":
            if current_play is None:
                current_play = {"uuid": None, "name": None, "counter": counter, "tasks": []}
                plays.append(current_play)
            current_task = {"uuid": data.get("task_uuid"), "name": data.get("task"), "action": data.get("task_action"), "counter": counter, "results": dict(RESULTS), "failed_hosts": [], "first_failure_counter": None}
            current_play["tasks"].append(current_task)
            if current_task["uuid"]:
                tasks_by_uuid[current_task["uuid"]] = current_task
        elif event in RUNNER_EVENTS:
            task = tasks_by_uuid.get(data.get("task_uuid")) or current_task
            if not task:
                continue
            if event == "runner_on_ok":
                key = "changed" if (data.get("res") or {}).get("changed") else "ok"
            elif event == "runner_on_failed":
                key = "failed"
            elif event == "runner_on_unreachable":
                key = "unreachable"
            else:
                key = "skipped"
            task["results"][key] += 1
            if key in {"failed", "unreachable"}:
                if task["first_failure_counter"] is None:
                    task["first_failure_counter"] = counter
                h = _host(host, data)
                if h and (key == "unreachable" or not data.get("ignore_errors")) and h not in task["failed_hosts"]:
                    task["failed_hosts"].append(h)
    return {"plays": plays}


def build_host_summary(rows) -> dict:
    hosts = {}
    totals = dict(RESULTS)
    for counter, event, host, payload in rows:
        if event.startswith("runner_item_on_") or event not in RUNNER_EVENTS:
            continue
        data = _event_data(payload)
        h = _host(host, data)
        if not h:
            continue
        row = hosts.setdefault(h, {"host": h, **dict(RESULTS), "status": "ok", "first_failure_counter": None})
        if event == "runner_on_ok":
            key = "changed" if (data.get("res") or {}).get("changed") else "ok"
        elif event == "runner_on_failed":
            key = "failed"
        elif event == "runner_on_unreachable":
            key = "unreachable"
        else:
            key = "skipped"
        row[key] += 1
        totals[key] += 1
        if key in {"failed", "unreachable"} and row["first_failure_counter"] is None:
            row["first_failure_counter"] = counter
    for row in hosts.values():
        row["status"] = "unreachable" if row["unreachable"] else "failed" if row["failed"] else "changed" if row["changed"] else "ok" if row["ok"] else "skipped"
    return {"hosts": sorted(hosts.values(), key=lambda r: (0 if r["status"] in {"failed", "unreachable"} else 1, r["host"])), "totals": totals}
