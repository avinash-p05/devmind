# Runbook: payment-service

Service: payment-service
Owner: payments team

## Dashboards

- Payment success rate, p95 latency, database pool in_use and wait_ms.

## Common alerts

- **Pool wait > 1 s**: connections are being held too long. Check for slow queries
  or external calls inside transactions before considering a larger pool.
- **5xx rate > 2%**: check the latest deploy in deployments/release-notes.md; roll
  back first if the alert started within 30 minutes of a release.
- **Card processor errors**: outbound retries follow config/retries.yaml; do not
  raise max_attempts during an incident.
