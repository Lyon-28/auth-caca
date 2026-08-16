import json
import asyncio
from fastapi.responses import StreamingResponse
from app.redis_client import redis

async def event_stream(channel: str):
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        yield "event: connected\ndata: {}\n\n"
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=25)
            if message and message["type"] == "message":
                yield f"data: {message['data']}\n\n"
            else:
                yield ": ping\n\n"
            await asyncio.sleep(0.5)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()

def sse_response(channel: str) -> StreamingResponse:
    return StreamingResponse(event_stream(channel), media_type="text/event-stream")

async def publish_event(channel: str, event: dict):
    await redis.publish(channel, json.dumps(event))