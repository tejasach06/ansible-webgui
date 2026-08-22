from app.db.models import HostResultStatus
from app.services.run_report import ReportBuilder


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

def test_report_builder_accumulates_events():
    builder = ReportBuilder(1)
    for counter, event, host, payload in rows():
        builder.handle(counter, event, host, payload)
    plays, tasks, host_results = builder.pending_plays, builder.pending_tasks, builder.pending_results

    assert len(plays) == 1
    assert len(tasks) == 2
    assert len(host_results) == 4

    statuses = [hr.status for hr in host_results]
    assert HostResultStatus.changed in statuses
    assert HostResultStatus.failed in statuses
    assert HostResultStatus.unreachable in statuses
    assert HostResultStatus.skipped in statuses
