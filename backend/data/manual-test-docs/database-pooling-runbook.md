# Database Pooling Runbook

## Recommended settings

The API uses a bounded PostgreSQL connection pool. Start with a pool size of 20
and a maximum overflow of 10 for the payment service. Increase these values only
after checking database CPU, memory, and active connection limits.

## Symptoms of exhaustion

Look for `QueuePool limit reached`, `connection checkout timed out`, or a sudden
increase in request latency. These messages indicate that requests are waiting
for an available database connection.

## Recovery

1. Check active database connections.
2. Compare worker concurrency with pool capacity.
3. Reduce application concurrency if the database is saturated.
4. Roll back the latest deployment if checkout timeouts continue.
