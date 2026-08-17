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


