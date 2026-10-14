# Payment Service Connection Pool Exhaustion

Incident ID: INC-2026-1187
Service: payment-service
Severity: SEV-1
Date: 2026-09-22

## Summary

Twelve minutes after payment-service v2.14.0 was deployed, card payments started
failing with HTTP 503. The database connection pool was exhausted: all 20
connections were checked out and new requests timed out after waiting 5 seconds
for a connection. About 38% of checkout payments failed during the incident.

## Timeline

- 14:02 UTC - payment-service v2.14.0 deployment started.
- 14:06 UTC - deployment completed on all 6 replicas.
- 14:10 UTC - `db.pool.exhausted` errors appear in payment-service logs.
- 14:14 UTC - payment error rate alert fires (SEV-1 declared).
- 14:21 UTC - on-call sees pool in_use=20/20 on every replica.
- 14:26 UTC - rollback to v2.13.4 started.
- 14:31 UTC - error rate back to baseline.

## Impact

- 38% of checkout payments failed with HTTP 503 for 21 minutes.
- No double charges; failed payments were never submitted to the card processor.

## Investigation

v2.14.0 added a synchronous call to the external fraud-check API inside the
database transaction that records the payment. Each request therefore held a
database connection for the full duration of the fraud-check call (p95 1.8 s).
Under normal peak traffic this kept every connection busy and the pool ran dry.

## Corrective Action

Rolled back to v2.13.4. The fraud-check call will be moved outside the
transaction so the connection is released before calling the external API.
See postmortems/payment-pool-exhaustion.md.
