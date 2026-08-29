import json
import os
import shutil
import tempfile

import ansible_runner
import redis

from app.core.config import settings
from app.core.time import utcnow
from app.db.models import JobEvent, JobRun, JobStatus, Playbook, Project
from app.db.session import SyncSessionLocal
from app.services.credentials import decrypt_payload
from app.services.run_report import ReportBuilder
from app.tasks.job_workspace import export_inventory_snapshot, export_project_snapshot, materialize_credentials
from app.tasks.worker import celery_app

redis_client = redis.Redis.from_url(settings.REDIS_URL)

@celery_app.task(name="run_job")
def run_job(job_run_id: int):
    db = SyncSessionLocal()
    try:
        job = db.query(JobRun).filter(JobRun.id == job_run_id).first()
        if not job:
            return
        
        job.status = JobStatus.running
        job.started_at = utcnow()
        db.commit()

        snapshot = job.params_snapshot
        playbook_row = db.query(Playbook).filter(Playbook.id == job.playbook_id).first()
        project = db.query(Project).filter(Project.id == playbook_row.project_id).first()

        temp_dir = tempfile.mkdtemp(dir=settings.ARTIFACT_ROOT)
        os.chmod(temp_dir, 0o700)

        try:
            proj_export = export_project_snapshot(project.name, temp_dir, snapshot.get("git_sha"))
            inventory_path = export_inventory_snapshot(
                temp_dir,
                snapshot["inventory_rel_path"],
                snapshot.get("inventory_git_sha"),
            )
            _, cmdline_extra = materialize_credentials(
                db,
                temp_dir,
                snapshot.get("credential_ids", []),
                snapshot,
            )

            cmdline_parts = list(cmdline_extra)
            if snapshot.get("diff"):
                cmdline_parts.append("--diff")
            cmdline_str = " ".join(cmdline_parts)
            extravars = dict(snapshot.get("extra_vars") or {})
            if job.survey_secrets_enc:
                extravars.update(json.loads(decrypt_payload(job.survey_secrets_enc)))

            events_batch = []
            event_counter = 0
            stats_from_event = None
            report_builder = ReportBuilder(job.id)

            def _flush_report():
                report_builder.flush(db)
            def event_handler(event_data):
                nonlocal event_counter, stats_from_event
                event_counter += 1
                if event_counter > 200000:
                    return

                stdout_text = event_data.get("stdout", "")
                if event_data.get("event") == "playbook_on_stats":
                    stats_from_event = event_data.get("event_data")
                if len(stdout_text) > 65536:
                    stdout_text = stdout_text[:65536] + "\n...[truncated]"

                report_builder.handle(event_counter, event_data.get("event", ""), event_data.get("host"), event_data)

                ev = JobEvent(
                    job_run_id=job.id,
                    counter=event_counter,
                    uuid=event_data.get("uuid", ""),
                    event=event_data.get("event", ""),
                    host=event_data.get("host"),
                    task=event_data.get("task"),
                    stdout=stdout_text,
                    payload=event_data
                )
                events_batch.append(ev)
                
                # Redis pubsub publish for live log tailing
                redis_client.publish(
                    f"job:{job.id}",
                    json.dumps({
                        "counter": event_counter,
                        "stdout": stdout_text,
                        "event": event_data.get("event")
                    })
                )

                if len(events_batch) >= 50:
                    db.bulk_save_objects(events_batch)
                    _flush_report()
                    db.commit()
                    events_batch.clear()
            def cancel_callback():
                return redis_client.get(f"job:{job.id}:cancel") == b"1"

            artifact_dir = os.path.join(settings.ARTIFACT_ROOT, str(job.id))

            runner = ansible_runner.run(
                private_data_dir=temp_dir,
                project_dir=proj_export,
                playbook=snapshot["playbook_rel_path"],
                inventory=inventory_path,
                extravars=extravars,
                limit=snapshot.get("limit"),
                tags=snapshot.get("tags"),
                skip_tags=snapshot.get("skip_tags"),
                verbosity=snapshot.get("verbosity", 0),
                forks=snapshot.get("forks", 5),
                envvars={
                    "ANSIBLE_FORCE_COLOR": "1",
                    "PY_COLORS": "1",
                    "ANSIBLE_STDOUT_CALLBACK": "default",
                    "ANSIBLE_COLLECTIONS_PATH": f"{os.path.join(proj_export, 'collections')}:/usr/share/ansible/collections",
                },
                cmdline=cmdline_str if cmdline_str else None,
                event_handler=event_handler,
                cancel_callback=cancel_callback,
                artifact_dir=artifact_dir,
                json_mode=False
            )

            if events_batch:
                db.bulk_save_objects(events_batch)
                _flush_report()
                db.commit()
            job.stats = runner.stats or stats_from_event
            job.rc = runner.rc
            job.artifact_dir = artifact_dir
            job.finished_at = utcnow()
            if cancel_callback():
                job.status = JobStatus.canceled
            elif runner.status == "successful":
                job.status = JobStatus.successful
            else:
                job.status = JobStatus.failed
            db.commit()
            from app.tasks.notify import send_notification
            send_notification.delay("job_finished", {"event": "job_finished", "job_id": job.id, "status": job.status.value, "mode": job.mode.value, "template_id": job.template_id, "playbook_id": job.playbook_id, "rc": job.rc, "stats": job.stats, "url": None})

        except Exception:
            job.status = JobStatus.failed
            job.finished_at = utcnow()
            db.commit()
            raise
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    finally:
        db.close()
