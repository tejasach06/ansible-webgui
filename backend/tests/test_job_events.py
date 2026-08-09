from app.services.job_events import build_host_summary, build_task_tree


def rows():
    return [
        (1, "playbook_on_play_start", None, {"event_data": {"play_uuid": "p1", "play": "Deploy"}}),
        (2, "playbook_on_task_start", None, {"event_data": {"task_uuid": "t1", "task": "Install", "task_action": "package"}}),
        (3, "runner_on_ok", "web1", {"event_data": {"task_uuid": "t1", "host": "web1", "res": {"changed": True}}}),
        (4, "runner_item_on_ok", "web1", {"event_data": {"task_uuid": "t1", "host": "web1", "res": {"changed": True}}}),
        (5, "playbook_on_task_start", None, {"event_data": {"task_uuid": "t2", "task": "Restart", "task_action": "service"}}),
        (6, "runner_on_failed", "web2", {"event_data": {"task_uuid": "t2", "host": "web2", "ignore_errors": False, "res": {}}}),
        (7, "runner_on_unreachable", "web3", {"event_data": {"task_uuid": "t2", "host": "web3", "res": {}}}),
        (8, "runner_on_skipped", "web4", {"event_data": {"task_uuid": "t2", "host": "web4", "res": {}}}),
    ]


def test_build_task_tree_counts_results_and_failures_once():
    tree = build_task_tree(rows())
    task1, task2 = tree["plays"][0]["tasks"]
    assert task1["results"] == {"ok": 0, "changed": 1, "failed": 0, "unreachable": 0, "skipped": 0}
    assert task2["failed_hosts"] == ["web2", "web3"]
    assert task2["first_failure_counter"] == 6


def test_build_host_summary_sets_status_precedence():
    summary = build_host_summary(rows())
    hosts = {row["host"]: row for row in summary["hosts"]}
    assert hosts["web3"]["status"] == "unreachable"
    assert hosts["web2"]["status"] == "failed"
    assert summary["totals"] == {"ok": 0, "changed": 1, "failed": 1, "unreachable": 1, "skipped": 1}
