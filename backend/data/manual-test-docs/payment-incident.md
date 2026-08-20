# Payment Service Incident

- **Service:** payment-service
- **Severity:** high
- **Incident date:** 2026-10-05

## Summary

The payment service started returning 503 responses after the latest deployment.
Checkout requests timed out because the PostgreSQL connection pool was exhausted.

## Evidence

The deployment increased concurrent request handling from 40 to 120 workers, but
the database pool remained configured with a maximum size of 20 connections.
Application logs showed `QueuePool limit reached` and `connection checkout timed out`.

## Root cause

The application concurrency limit was increased without increasing the database
connection pool capacity or adding request backpressure.

## Resolution

The team rolled back the deployment, reduced worker concurrency, and increased the
pool size after confirming the database server capacity.
