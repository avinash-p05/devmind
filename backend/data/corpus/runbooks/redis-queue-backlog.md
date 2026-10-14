# Runbook: Redis Queue Backlog

Use when a Redis-backed worker queue (notifications, image jobs, ingestion) grows
instead of draining.

1. Measure the backlog: `redis-cli LLEN <queue>`; run it twice, 60 s apart.
2. Compare consumption with production: if the queue grows while workers are
   healthy, workers are too slow, not broken.
3. Check recent deploys for changes to worker batch size or concurrency. Both
   notification-service (batch size) and image-processing (concurrency) have had
   incidents caused by lowering these values.
4. Mitigate by scaling worker replicas, then restore the previous batch size or
   concurrency.
5. Redis memory: alert if `used_memory` exceeds 75% of `maxmemory`; a backlog that
   reaches maxmemory makes producers fail.
