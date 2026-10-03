# Inventory Synchronization Incident

Incident ID: INC-2026-6173
Service: inventory-sync
Severity: SEV-2
Date: 2026-10-01

## Summary

Inventory synchronization jobs began failing after inventory-sync version 3.8.0
was deployed.

The failures occurred when the service attempted to communicate with the
warehouse API.

## Timeline

- 07:00 UTC - inventory-sync v3.8.0 deployment started.
- 07:05 UTC - deployment completed.
- 07:09 UTC - synchronization failures began.
- 07:15 UTC - HTTP 502 errors from warehouse API were observed.
- 07:23 UTC - outbound request configuration was investigated.
- 07:31 UTC - request timeout configuration was identified.
- 07:40 UTC - timeout value was corrected.
- 07:48 UTC - synchronization jobs recovered.

## Impact

- Inventory updates were delayed.
- Approximately 17% of synchronization jobs initially failed.
- Jobs were successfully retried after the configuration was corrected.

## Investigation

Version 3.8.0 reduced the warehouse API client timeout from 30 seconds to
5 seconds.

The warehouse API occasionally required more than five seconds to respond during
normal peak traffic.

The shorter timeout caused otherwise successful requests to be terminated early.

## Corrective Action

The timeout was restored to 30 seconds.

Future deployment validation should compare external API timeout settings with
observed service latency and retry behavior.