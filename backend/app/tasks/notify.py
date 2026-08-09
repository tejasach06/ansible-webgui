import httpx

from app.db.models import Notification, NotificationKind
from app.db.session import SyncSessionLocal
from app.tasks.worker import celery_app


@celery_app.task(name="send_notification")
def send_notification(event_type: str, payload: dict) -> None:
    db = SyncSessionLocal()
    try:
        rows = db.query(Notification).filter(Notification.enabled.is_(True)).all()
        for n in rows:
            if event_type == "approval_needed" and not n.on_approval_needed:
                continue
            if event_type == "job_finished" and payload.get("status") == "successful" and not n.on_success:
                continue
            if event_type == "job_finished" and payload.get("status") != "successful" and not n.on_failure:
                continue
            try:
                if n.kind == NotificationKind.slack:
                    text = f"Job #{payload.get('job_id')} needs approval ({payload.get('mode')})" if event_type == "approval_needed" else f"Job #{payload.get('job_id')} {payload.get('status')} ({payload.get('mode')}, rc={payload.get('rc')})"
                    httpx.post(n.url, json={"text": text}, timeout=10.0)
                else:
                    httpx.post(n.url, json=payload, timeout=10.0)
            except Exception:
                continue
    finally:
        db.close()
