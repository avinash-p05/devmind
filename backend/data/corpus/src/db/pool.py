"""Database connection pool for payment-service.

One asyncpg pool per process, created at startup and shared by every request.
Requests borrow a connection with `async with connection():` and must give it back
quickly; holding a connection across an external HTTP call starves the pool
(see incidents/payment-pool-exhaustion.md).
"""

import logging
from contextlib import asynccontextmanager

import asyncpg

from payment.settings import settings

log = logging.getLogger("db.pool")

ACQUIRE_TIMEOUT_SECONDS = 5.0
_pool: asyncpg.Pool | None = None


class PoolExhaustedError(RuntimeError):
    """No connection became free within ACQUIRE_TIMEOUT_SECONDS."""


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=5,
        max_size=settings.db_pool_size,  # DB_POOL_SIZE, default 20; see docs/database.md
        max_inactive_connection_lifetime=300,
    )
    return _pool


async def close_pool() -> None:
    if _pool is not None:
        await _pool.close()


@asynccontextmanager
async def connection():
    try:
        conn = await _pool.acquire(timeout=ACQUIRE_TIMEOUT_SECONDS)
    except TimeoutError as error:
        log.error(
            "db.pool.exhausted waited=%dms pool_size=%d",
            ACQUIRE_TIMEOUT_SECONDS * 1000,
            settings.db_pool_size,
        )
        raise PoolExhaustedError from error
    try:
        yield conn
    finally:
        await _pool.release(conn)
