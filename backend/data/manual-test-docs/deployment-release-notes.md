# Deployment Release Notes

## Release 2026.10.05.1

This release increased payment-service worker concurrency from 40 to 120 and
enabled the new checkout timeout configuration. The PostgreSQL pool settings were
not changed in this release.

## Rollback criteria

Roll back if payment 5xx responses exceed 2 percent for five minutes, checkout
latency exceeds 3 seconds, or database pool checkout timeouts appear in logs.
