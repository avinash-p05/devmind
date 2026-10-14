"""notification-service worker: pops messages from the Redis list and delivers them."""

import os

import redis

QUEUE = "notifications:outbound"
# Messages taken from Redis per loop. Lowering this reduces throughput linearly;
# v5.1.0 changed it from 100 to 25 and caused INC-2026-4128.
BATCH_SIZE = int(os.environ.get("NOTIFICATION_BATCH_SIZE", "100"))


def run(client: redis.Redis, deliver) -> None:
    while True:
        batch = client.lpop(QUEUE, BATCH_SIZE)
        if not batch:
            client.blpop(QUEUE, timeout=5)
            continue
        for message in batch:
            deliver(message)
