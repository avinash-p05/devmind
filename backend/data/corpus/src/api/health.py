"""Health endpoints shared by DevMind-managed services.

/healthz is the liveness probe: the process is up. It never touches dependencies,
so a database outage does not make Kubernetes restart every pod.
/readyz is the readiness probe: it checks PostgreSQL and Redis and returns 503 when
either is unreachable, which takes the pod out of the load balancer.
"""

from fastapi import APIRouter, Response

from app.dependencies import database, redis_client

router = APIRouter()


@router.get("/healthz")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(response: Response) -> dict:
    checks = {"postgres": await database.ping(), "redis": await redis_client.ping()}
    if not all(checks.values()):
        response.status_code = 503
    return {"status": "ready" if all(checks.values()) else "not_ready", "checks": checks}
