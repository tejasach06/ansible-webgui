from datetime import datetime

from app.db.models import HostResultStatus, JobHostResult, JobPlay, JobTask

RUNNER_EVENTS = {"runner_on_ok", "runner_on_failed", "runner_on_unreachable", "runner_on_skipped"}
REPORT_EVENTS = {"playbook_on_play_start", "playbook_on_task_start", *RUNNER_EVENTS}
RESULTS = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0}


def event_data(payload):
    return (payload or {}).get("event_data") or {}


def event_host(payload):
    data = event_data(payload)
    return payload.get("host") or data.get("host")


def result_status(event: str, data: dict) -> HostResultStatus | None:
    if event == "runner_on_ok":
        return HostResultStatus.changed if (data.get("res") or {}).get("changed") else HostResultStatus.ok
    if event == "runner_on_failed":
        return HostResultStatus.failed
    if event == "runner_on_unreachable":
        return HostResultStatus.unreachable
    if event == "runner_on_skipped":
        return HostResultStatus.skipped
    return None


def parse_timestamp(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def duration_ms(data: dict):
    value = data.get("duration") or (data.get("res") or {}).get("duration")
    if value is not None:
        try:
            return int(float(value) * 1000)
        except (TypeError, ValueError):
            return None
    start = parse_timestamp(data.get("start"))
    end = parse_timestamp(data.get("end"))
    if start and end:
        return int((end - start).total_seconds() * 1000)
    return None


class ReportBuilder:
    def __init__(self, job_run_id: int):
        self.job_run_id = job_run_id
        self.current_play = None
        self.current_task = None
        self.plays_by_uuid = {}
        self.tasks_by_uuid = {}
        self.pending_plays = []
        self.pending_tasks = []
        self.pending_results = []

    def handle(self, counter: int, event: str, host: str | None, payload: dict) -> None:
        p = dict(payload)
        if "event" not in p and event:
            p["event"] = event
        self.process(p, counter)

    def pending(self):
        return self.pending_plays, self.pending_tasks, self.pending_results
    def process(self, payload: dict, counter: int):
        event = payload.get("event", "")
        if event.startswith("runner_item_on_") or event not in REPORT_EVENTS:
            return
        data = event_data(payload)
        if event == "playbook_on_play_start":
            self._play_started(payload, data, counter)
        elif event == "playbook_on_task_start":
            self._task_started(payload, data, counter)
        elif event in RUNNER_EVENTS:
            self._host_result(payload, data, counter)

    def _play_started(self, payload: dict, data: dict, counter: int):
        uuid = data.get("play_uuid") or payload.get("uuid") or f"play:{counter}"
        play = JobPlay(
            job_run_id=self.job_run_id,
            uuid=uuid,
            name=data.get("play"),
            counter=counter,
            started_at=parse_timestamp(data.get("start")),
        )
        self.current_play = play
        self.plays_by_uuid[uuid] = play
        self.pending_plays.append(play)

    def _ensure_play(self, counter: int):
        if self.current_play is not None:
            return self.current_play
        uuid = f"implicit:{self.job_run_id}"
        play = self.plays_by_uuid.get(uuid)
        if play is None:
            play = JobPlay(job_run_id=self.job_run_id, uuid=uuid, name=None, counter=counter)
            self.plays_by_uuid[uuid] = play
            self.pending_plays.append(play)
        self.current_play = play
        return play

    def _task_started(self, payload: dict, data: dict, counter: int):
        play = self._ensure_play(counter)
        uuid = data.get("task_uuid") or payload.get("uuid") or f"task:{counter}"
        task = JobTask(
            job_run_id=self.job_run_id,
            play_id=play.id,
            uuid=uuid,
            name=data.get("task"),
            action=data.get("task_action"),
            counter=counter,
            started_at=parse_timestamp(data.get("start")),
        )
        task._report_play = play
        self.current_task = task
        self.tasks_by_uuid[uuid] = task
        self.pending_tasks.append(task)

    def _host_result(self, payload: dict, data: dict, counter: int):
        task = self.tasks_by_uuid.get(data.get("task_uuid")) or self.current_task
        host = event_host(payload)
        status = result_status(payload.get("event", ""), data)
        if task is None or not host or status is None:
            return
        result = JobHostResult(
            job_run_id=self.job_run_id,
            task_id=task.id,
            host=host,
            status=status,
            duration_ms=duration_ms(data),
            counter=counter,
            ignore_errors=bool(data.get("ignore_errors")),
            res=data.get("res"),
        )
        result._report_task = task
        self.pending_results.append(result)

    def flush(self, db):
        if self.pending_plays:
            db.add_all(self.pending_plays)
            db.flush()
            self.pending_plays.clear()
        if self.pending_tasks:
            for task in self.pending_tasks:
                if not task.play_id:
                    task.play_id = task._report_play.id
            db.add_all(self.pending_tasks)
            db.flush()
            self.pending_tasks.clear()
        if self.pending_results:
            for result in self.pending_results:
                if not result.task_id:
                    result.task_id = result._report_task.id
            db.add_all(self.pending_results)
            db.flush()
            self.pending_results.clear()
