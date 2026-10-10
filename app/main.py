"""pulse-api: a small FastAPI service used as the shared workload across the portfolio.

Run with:  uvicorn --factory app.main:create_app
"""

from __future__ import annotations

import logging
import socket
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from math import isqrt

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from app.config import Settings
from app.faults import FaultState, admin_router, apply_faults
from app.observability import Metrics, configure_logging

log = logging.getLogger("pulse")

# Probe and scrape endpoints are hit every few seconds; log them at DEBUG to keep logs useful.
_QUIET_ROUTES = {"/health", "/ready", "/metrics"}


class PrimeResult(BaseModel):
    n: int
    prime_count: int
    largest_prime: int | None


def count_primes(n: int) -> tuple[int, int | None]:
    """Sieve of Eratosthenes: number of primes <= n and the largest one."""
    if n < 2:
        return 0, None
    sieve = bytearray([1]) * (n + 1)
    sieve[0:2] = b"\x00\x00"
    for i in range(2, isqrt(n) + 1):
        if sieve[i]:
            sieve[i * i :: i] = bytes(len(range(i * i, n + 1, i)))
    return sum(sieve), sieve.rindex(1)


api_router = APIRouter(prefix="/api/v1", tags=["api"], dependencies=[Depends(apply_faults)])


@api_router.get("/info")
def info(request: Request) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    return {
        "service": settings.service_name,
        "version": settings.version,
        "environment": settings.environment,
        "hostname": socket.gethostname(),  # pod name in Kubernetes: shows load balancing
    }


@api_router.get("/primes/{n}")
def primes(request: Request, n: int = Path(ge=0)) -> PrimeResult:
    # Sync handler: FastAPI runs it in a worker thread, so CPU work doesn't block the event loop.
    limit = request.app.state.settings.max_prime_limit
    if n > limit:
        raise HTTPException(status_code=422, detail=f"n must be <= {limit}")
    count, largest = count_primes(n)
    return PrimeResult(n=n, prime_count=count, largest_prime=largest)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    metrics = Metrics(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.started = True
        metrics.ready.set(1)
        log.info(
            "startup complete",
            extra={"fields": {"version": settings.version, "environment": settings.environment}},
        )
        yield
        # Withdraw readiness first so load balancers stop sending traffic during shutdown.
        app.state.started = False
        metrics.ready.set(0)
        log.info("shutdown: readiness withdrawn")

    app = FastAPI(title=settings.service_name, version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    app.state.metrics = metrics
    app.state.faults = FaultState()
    app.state.started = False

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        start = time.perf_counter()
        status = 500
        metrics.in_progress.inc()
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            log.exception("unhandled error", extra={"fields": {"request_id": request_id}})
            raise
        finally:
            elapsed = time.perf_counter() - start
            metrics.in_progress.dec()
            # Label by route template, never raw path, to keep metric cardinality bounded.
            matched = request.scope.get("route")
            route = getattr(matched, "path", "<unmatched>")
            metrics.requests.labels(request.method, route, str(status)).inc()
            metrics.latency.labels(request.method, route).observe(elapsed)
            level = logging.DEBUG if route in _QUIET_ROUTES and status < 400 else logging.INFO
            if status >= 500:
                level = logging.ERROR
            log.log(
                level,
                "request",
                extra={
                    "fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "route": route,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 2),
                        "client": request.client.host if request.client else None,
                    }
                },
            )

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        # Liveness: the process can serve HTTP. Deliberately checks no dependencies.
        return {"status": "ok"}

    @app.get("/ready", tags=["ops"])
    def ready(request: Request) -> JSONResponse:
        if not request.app.state.started:
            return JSONResponse({"status": "not-ready", "reason": "starting or shutting down"}, 503)
        if request.app.state.faults.force_not_ready:
            return JSONResponse({"status": "not-ready", "reason": "forced by fault injection"}, 503)
        return JSONResponse({"status": "ready"})

    @app.get("/metrics", tags=["ops"])
    def prometheus_metrics() -> Response:
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    app.include_router(api_router)
    if settings.fault_injection_enabled:
        app.include_router(admin_router)
        log.warning("fault injection API enabled at /admin/faults")
    return app
