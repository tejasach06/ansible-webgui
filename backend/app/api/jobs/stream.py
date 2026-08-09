import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.models import JobEvent, User
from app.db.session import get_db
from app.core.config import settings


router = APIRouter()


@router.get("/{job_id}/events/stream")
async def stream_job_events(
    job_id: int,
    request: Request,
    after_counter: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    async def event_generator():
        # Replay DB events past after_counter
        events = (await db.execute(
            select(JobEvent)
            .where(JobEvent.job_run_id == job_id, JobEvent.counter > after_counter)
            .order_by(JobEvent.counter.asc())
        )).scalars().all()

        last_counter = after_counter
        for ev in events:
            last_counter = ev.counter
            data = json.dumps({"counter": ev.counter, "stdout": ev.stdout, "event": ev.event})
            yield f"id: {ev.counter}\ndata: {data}\n\n"

        # Pubsub subscription for new events
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"job:{job_id}")

        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if message:
                    payload = json.loads(message["data"])
                    if payload["counter"] > last_counter:
                        last_counter = payload["counter"]
                        yield f"id: {payload['counter']}\ndata: {message['data'].decode()}\n\n"
                else:
                    # Heartbeat comment
                    yield ": heartbeat\n\n"
        finally:
            await pubsub.unsubscribe(f"job:{job_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
