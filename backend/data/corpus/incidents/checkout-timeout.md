# Checkout Request Timeout Incident

Incident ID: INC-2026-1203
Service: checkout-service
Severity: SEV-2
Date: 2026-09-28

## Summary

Checkout requests stalled for up to 60 seconds and then failed. inventory-service
was degraded during a database failover and stopped answering stock reservation
requests. checkout-service called the reservation endpoint without a client
timeout, so request threads blocked until the load balancer cut them off.

## Timeline

- 10:15 UTC - inventory-service database failover begins.
- 10:16 UTC - checkout p99 latency rises above 30 s.
- 10:19 UTC - checkout-service thread pool saturated; health checks start failing.
- 10:34 UTC - inventory-service recovers; checkout drains its backlog.

## Investigation

The HTTP client used for `POST /reservations` had no timeout configured, so it
fell back to the library default of no timeout. A slow dependency became a full
checkout outage because every worker thread waited on it.

## Corrective Action

- Set a 2 second timeout on inventory reservation calls.
- Wrap the call in a circuit breaker that opens after 5 consecutive failures.
- Show "stock check unavailable, try again" instead of hanging the request.
