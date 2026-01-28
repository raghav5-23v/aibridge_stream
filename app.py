from gevent import monkey

monkey.patch_all()

import os
import json
import time
import redis
from flask import Flask, Response, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

REDIS_HOST = os.getenv("CACHE_REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("CACHE_REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("CACHE_REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("CACHE_REDIS_PASSWORD", "redis")

redis_client = redis.StrictRedis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
)


def get_time():
    return time.time()


def event_stream(session_id):

    channel_name = f"chat_stream:{session_id}"
    pubsub = redis_client.pubsub()
    pubsub.subscribe(channel_name)

    # yield f"data: {json.dumps({'status': 'connected'})}\n\n"

    yield f"event: connected\ndata : {json.dumps({'session_id': session_id, 'channel': channel_name})}\n\n"

    ping_interval = 30
    last_ping = get_time()

    try:
        for message in pubsub.listen():
            current_time = get_time()

            if current_time - last_ping > ping_interval:
                yield f"event: ping\ndata: {json.dumps({'time': current_time})}\n\n"
                last_ping = current_time

            if message["type"] == "message":
                data = message["data"]

                if data == "__STOP__":
                    break

                try:
                    parsed = json.loads(data)
                    event_type = parsed.get("type", "message")

                    yield f"event: {event_type}\ndata: {data}\n\n"

                except json.JSONDecodeError:
                    yield f"data: {data}\n\n"
    except GeneratorExit:
        print(f"Client disconnected: {session_id}")

    except Exception as e:
        print(f"Stream Error: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    finally:
        pubsub.unsubscribe(channel_name)
        pubsub.close()


@app.route("/health", methods=["GET"])
def health():
    if redis_client.ping():
        return "OK", 200

    return "Unhealthy", 500


@app.route("/api/v1.0/a1/stream/<session_id>", methods=["GET"])
def stream(session_id):
    return Response(
        event_stream(session_id),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100)
