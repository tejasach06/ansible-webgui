from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.models import HostResultStatus, JobHostResult, JobPlay, JobTask

RUNNER_EVENTS = {"runner_on_ok", "runner_on_failed", "runner_on_unreachable", "runner_on_skipped"}
REPORT_EVENTS = {"playbook_on_play_start", "playbook_on_task_start", *RUNNER_EVENTS}


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
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
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

    def handle(self, counter: int, event: str, _host: str | None, payload: dict) -> None:
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
        if self.current_play and not self.current_play.finished_at:
            self.current_play.finished_at = parse_timestamp(data.get("start")) or utcnow()
        uuid = data.get("play_uuid") or payload.get("uuid") or f"play:{counter}"
        play = JobPlay(
            job_run_id=self.job_run_id,
            uuid=uuid,
            name=data.get("play"),
            counter=counter,
            started_at=parse_timestamp(data.get("start")) or utcnow(),
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
        if self.current_task and not self.current_task.finished_at:
            self.current_task.finished_at = parse_timestamp(data.get("start")) or utcnow()
        uuid = data.get("task_uuid") or payload.get("uuid") or f"task:{counter}"
        task = JobTask(
            job_run_id=self.job_run_id,
            play_id=play.id,
            uuid=uuid,
            name=data.get("task"),
            action=data.get("task_action"),
            counter=counter,
            started_at=parse_timestamp(data.get("start")) or utcnow(),
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
        if data.get("end"):
            end_time = parse_timestamp(data.get("end")) or utcnow()
            task.finished_at = end_time
            if self.current_play:
                self.current_play.finished_at = end_time
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


async def build_report(db: AsyncSession, job_id: int) -> dict:
    plays = (await db.execute(select(JobPlay).where(JobPlay.job_run_id == job_id).order_by(JobPlay.counter.asc()))).scalars().all()
    tasks = (await db.execute(select(JobTask).where(JobTask.job_run_id == job_id).order_by(JobTask.counter.asc()))).scalars().all()
    host_results = (await db.execute(select(JobHostResult).where(JobHostResult.job_run_id == job_id).order_by(JobHostResult.counter.asc()))).scalars().all()

    hr_by_task = {}
    hr_by_host = {}
    totals = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0}

    for hr in host_results:
        st = hr.status.value if hasattr(hr.status, "value") else str(hr.status)
        totals[st] = totals.get(st, 0) + 1

        if hr.task_id not in hr_by_task:
            hr_by_task[hr.task_id] = []
        hr_by_task[hr.task_id].append(hr)

        if hr.host not in hr_by_host:
            hr_by_host[hr.host] = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0, "first_failure_counter": None}
        hr_by_host[hr.host][st] = hr_by_host[hr.host].get(st, 0) + 1

        if st in ("failed", "unreachable"):
            ffc = hr_by_host[hr.host]["first_failure_counter"]
            if ffc is None or hr.counter < ffc:
                hr_by_host[hr.host]["first_failure_counter"] = hr.counter

    tasks_by_play = {}
    for task in tasks:
        t_hrs = hr_by_task.get(task.id, [])
        res = {"ok": 0, "changed": 0, "failed": 0, "unreachable": 0, "skipped": 0}
        failed_hosts = []
        first_fail_counter = None
        durations = []

        for hr in t_hrs:
            st = hr.status.value if hasattr(hr.status, "value") else str(hr.status)
            res[st] = res.get(st, 0) + 1
            if hr.duration_ms is not None:
                durations.append(hr.duration_ms)

            is_failed = (st == "unreachable") or (st == "failed" and not hr.ignore_errors)
            if is_failed:
                if hr.host not in failed_hosts:
                    failed_hosts.append(hr.host)
                if first_fail_counter is None or hr.counter < first_fail_counter:
                    first_fail_counter = hr.counter

        task_dict = {
            "uuid": task.uuid,
            "name": task.name,
            "action": task.action,
            "duration_ms": max(durations) if durations else 0,
            "results": res,
            "failed_hosts": failed_hosts,
            "first_failure_counter": first_fail_counter,
        }

        if task.play_id not in tasks_by_play:
            tasks_by_play[task.play_id] = []
        tasks_by_play[task.play_id].append(task_dict)

    plays_list = []
    for play in plays:
        p_tasks = tasks_by_play.get(play.id, [])
        p_durations = [t["duration_ms"] for t in p_tasks]
        plays_list.append({
            "uuid": play.uuid,
            "name": play.name,
            "duration_ms": sum(p_durations),
            "tasks": p_tasks,
        })

    hosts_list = []
    for host_name, stats in hr_by_host.items():
        if stats["unreachable"] > 0:
            st = "unreachable"
        elif stats["failed"] > 0:
            st = "failed"
        elif stats["changed"] > 0:
            st = "changed"
        elif stats["ok"] > 0:
            st = "ok"
        else:
            st = "skipped"

        hosts_list.append({
            "host": host_name,
            "ok": stats["ok"],
            "changed": stats["changed"],
            "failed": stats["failed"],
            "unreachable": stats["unreachable"],
            "skipped": stats["skipped"],
            "status": st,
            "first_failure_counter": stats["first_failure_counter"],
        })

    hosts_list.sort(key=lambda h: (0 if h["status"] in ("failed", "unreachable") else 1, h["host"]))

    return {
        "plays": plays_list,
        "hosts": hosts_list,
        "totals": totals,
    }
