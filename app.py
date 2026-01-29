import os
import json
import time
import asyncio
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.getenv("CACHE_REDIS_HOST", "")
REDIS_PORT = int(os.getenv("CACHE_REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("CACHE_REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("CACHE_REDIS_PASSWORD", "redis")

# REDIS_HOST = "18.214.160.94"
# REDIS_PORT = 6379
# REDIS_DB = 0
# REDIS_PASSWORD = "redis"

redis_client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
)


def get_time():
    return time.time()


async def event_generator(session_id: str):
    channel_name = f"chat_stream:{session_id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)

    yield {
        "event": "connected",
        "data": json.dumps({"session_id": session_id, "channel": channel_name}),
    }

    ping_interval = 30
    last_ping = get_time()

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )

            current_time = get_time()
            if current_time - last_ping > ping_interval:
                yield {"event": "ping", "data": json.dumps({"time": current_time})}
                last_ping = current_time

            if message:
                data = message["data"]

                if data == "__STOP__":
                    break

                try:
                    parsed = json.loads(data)
                    event_type = parsed.get("type", "message")
                    yield {"event": event_type, "data": data}

                except json.JSONDecodeError:
                    yield {"data": data}

            await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        print(f"Client disconnected: {session_id}")
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()


@app.get("/health")
async def health():
    try:
        if await redis_client.ping():
            return {"status": "ok"}
    except Exception:
        pass
    return Response("Unhealthy", status_code=500)


@app.get("/api/v1.0/a1/stream/{session_id}")
async def stream(session_id: str):
    return EventSourceResponse(
        event_generator(session_id),
        headers={
            "Cache-Control": "co-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5100)
