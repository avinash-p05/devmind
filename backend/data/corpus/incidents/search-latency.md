# Search Service Performance Incident

Incident ID: INC-2026-5086
Service: search-service
Severity: SEV-2
Date: 2026-10-02

## Summary

Search API latency increased significantly after search-service version 7.4.0
was deployed.

The service continued returning correct search results, but database queries
became progressively slower as traffic increased.

## Timeline

- 13:00 UTC - search-service v7.4.0 deployment started.
- 13:05 UTC - deployment completed.
- 13:12 UTC - p95 search latency increased.
- 13:18 UTC - PostgreSQL CPU utilization increased.
- 13:27 UTC - slow query analysis started.
- 13:39 UTC - query execution plan identified a sequential scan.
- 13:48 UTC - missing index was identified.
- 14:02 UTC - PostgreSQL index was created.
- 14:08 UTC - search latency returned to normal.

## Impact

- Search p95 latency increased from 180 ms to 2.4 seconds.
- Search requests occasionally timed out.
- No incorrect search results were observed.

## Investigation

A new query introduced in version 7.4.0 filtered search records using the
`tenant_id` and `created_at` columns.

PostgreSQL did not have a suitable composite index for this access pattern.

As a result, PostgreSQL performed sequential scans over a large portion of the
search table.

## Corrective Action

A composite index on `tenant_id` and `created_at` was created.

Database query plans for high-traffic queries should be reviewed before future
deployments.