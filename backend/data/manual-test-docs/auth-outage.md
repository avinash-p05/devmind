# Authentication Service Incident

Incident ID: INC-2026-2017
Service: auth-service
Severity: SEV-1
Date: 2026-10-05

## Summary

Shortly after auth-service version 4.3.0 was deployed to production, authentication
requests began failing intermittently. Approximately 31% of login requests returned
HTTP 401 or HTTP 500 responses during the incident.

The service itself remained reachable and CPU and memory utilization were normal.

## Timeline

- 09:00 UTC - auth-service v4.3.0 deployment started.
- 09:04 UTC - deployment completed across all production instances.
- 09:07 UTC - authentication error rate began increasing.
- 09:10 UTC - first SEV-1 alert triggered.
- 09:16 UTC - investigation identified failures during token signing.
- 09:22 UTC - certificate configuration was identified as suspicious.
- 09:29 UTC - deployment rollback started.
- 09:34 UTC - authentication error rate returned to normal.

## Impact

- 31% of login requests failed.
- Existing authenticated sessions were mostly unaffected.
- New login attempts were affected.
- No database corruption occurred.

## Investigation

Application logs showed failures while loading the OAuth signing certificate.
The certificate configured in v4.3.0 had expired before the deployment.

The previous production version used the older valid certificate.

## Corrective Action

The deployment was rolled back to v4.2.7.

Before the next deployment, certificate expiry validation must be added to the
deployment pipeline.