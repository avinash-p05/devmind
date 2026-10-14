# Database Guide: PostgreSQL Connection Pooling

Every service that talks to the shared PostgreSQL cluster uses a fixed-size
connection pool. Read this before changing `DB_POOL_SIZE` for any service.

## How connections are shared

A process opens its pool at startup. Each request borrows a connection, runs its
queries and returns the connection to the pool, so many concurrent requests share
a small number of long-lived database connections. Opening a new connection per
request would cost a TCP + TLS + auth handshake every time.

## Choosing the pool size

PostgreSQL is configured with `max_connections = 200`. We reserve 20 connections
for migrations, admin sessions and monitoring. The rest is split across replicas:

    pool_size = (max_connections - reserved) / total_replicas

payment-service runs 6 replicas and shares the cluster with checkout-service
(3 replicas), so (200 - 20) / 9 = 20 connections per replica. That is why
`DB_POOL_SIZE` is 20 and there is no headroom to raise it without adding
PgBouncer or reducing replicas.

## Rules

- Never hold a connection while calling another service.
- Keep transactions short; pool wait time above 1 s is an alerting condition.
