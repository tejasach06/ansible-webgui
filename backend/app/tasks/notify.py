import httpx

from app.db import session as db_session
from app.db.models import Notification, NotificationKind
from app.tasks.worker import celery_app


@celery_app.task(name="deliver_notification", bind=True, max_retries=3)
def deliver_notification(self, kind_value: str, url: str, json_body: dict) -> None:  # noqa: ARG001
    try:
        httpx.post(url, json=json_body, timeout=10.0)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5) from exc


@celery_app.task(name="send_notification")
def send_notification(event_type: str, payload: dict) -> None:
    db = db_session.SyncSessionLocal()
    try:
        rows = db.query(Notification).filter(Notification.enabled.is_(True)).all()
        for n in rows:
            if event_type == "approval_needed" and not n.on_approval_needed:
                continue
            if event_type == "job_finished" and payload.get("status") == "successful" and not n.on_success:
                continue
            if event_type == "job_finished" and payload.get("status") != "successful" and not n.on_failure:
                continue

            if n.kind == NotificationKind.slack:
                text = (
                    f"Job #{payload.get('job_id')} needs approval ({payload.get('mode')})"
                    if event_type == "approval_needed"
                    else f"Job #{payload.get('job_id')} {payload.get('status')} ({payload.get('mode')}, rc={payload.get('rc')})"
                )
                body = {"text": text}
            else:
                body = payload

            deliver_notification.delay(n.kind.value, n.url, body)
    finally:
        db.close()
