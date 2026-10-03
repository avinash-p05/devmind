# Notification Service Delay Incident

Incident ID: INC-2026-4128
Service: notification-service
Severity: SEV-2
Date: 2026-10-03

## Summary

Notification delivery became delayed after a production deployment of the
notification-service.

Email and push notifications were successfully generated but remained in the
Redis-backed queue for an extended period before workers processed them.

## Timeline

- 11:00 UTC - notification-service v5.1.0 deployment started.
- 11:06 UTC - deployment completed.
- 11:15 UTC - Redis queue depth started increasing.
- 11:22 UTC - notification delivery latency exceeded five minutes.
- 11:30 UTC - Redis queue inspection began.
- 11:37 UTC - worker processing rate was found to be below incoming message rate.
- 11:45 UTC - worker replicas were increased.
- 11:56 UTC - queue depth returned to normal.

## Impact

- Notification delivery was delayed.
- Approximately 24% of notifications exceeded the five-minute delivery target.
- No messages were permanently lost.

## Investigation

Redis itself was healthy and available.

The deployment changed the notification worker batch size from 100 messages to
25 messages.

At the existing worker count, the reduced batch size caused the workers to process
messages more slowly than they were being produced.

The Redis queue therefore accumulated a backlog.

## Corrective Action

Worker capacity was increased and the batch size was restored to 100.

Queue depth and processing rate should be monitored together during future
deployments.