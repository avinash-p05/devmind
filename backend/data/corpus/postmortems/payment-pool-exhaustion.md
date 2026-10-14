# Postmortem: payment-service pool exhaustion (INC-2026-1187)

Service: payment-service
Severity: SEV-1
Date: 2026-09-22

## Why we rolled back instead of scaling up

The recommendation to roll back to v2.13.4 was based on three pieces of evidence:

1. Errors started 4 minutes after the v2.14.0 rollout finished, and v2.14.0 was the
   only change shipped to payment-service that day.
2. Pool wait time rose on every replica at the same time, which points at a code
   change rather than a single unhealthy host.
3. Increasing the pool size was not safe: the database already serves 6 replicas
   and the pool-sizing rule in docs/database.md leaves no headroom.

## Root cause

The fraud-check HTTP call introduced in v2.14.0 ran while a database connection
was held open, so connection hold time grew from ~40 ms to ~1.8 s.

## Action items

- Release the database connection before any external HTTP call (owner: payments team).
- Alert when pool wait time exceeds 1 second for 2 minutes.
- Add a load test that runs the fraud-check path at peak traffic before release.
