"""Opt-in fault injection used by the observability/incident lab.

Disabled by default. When FAULT_INJECTION_ENABLED=true the /admin/faults API
(token protected) can add latency, return HTTP 500s, or fail readiness.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import random
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger("pulse.faults")


@dataclass
class FaultState:
    latency_ms: int = 0
    error_rate: float = 0.0
    force_not_ready: bool = False


class FaultConfig(BaseModel):
    latency_ms: int = Field(default=0, ge=0, le=10_000)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    force_not_ready: bool = False


async def apply_faults(request: Request) -> None:
    """Dependency on /api routes; a no-op unless faults have been configured."""
    faults: FaultState = request.app.state.faults
    if faults.latency_ms:
        await asyncio.sleep(faults.latency_ms / 1000)
    # Non-cryptographic randomness is fine for a lab error ratio.
    if faults.error_rate and random.random() < faults.error_rate:  # noqa: S311
        log.error("injected fault", extra={"fields": {"path": request.url.path, "fault": "http_500"}})
        raise HTTPException(status_code=500, detail="injected fault")


def require_admin(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.admin_token
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="invalid or missing X-Admin-Token")


admin_router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _publish(request: Request, state: FaultState) -> FaultConfig:
    metrics = request.app.state.metrics
    metrics.fault_latency.set(state.latency_ms / 1000)
    metrics.fault_error_ratio.set(state.error_rate)
    return FaultConfig(**state.__dict__)


@admin_router.get("/faults")
def get_faults(request: Request) -> FaultConfig:
    return FaultConfig(**request.app.state.faults.__dict__)


@admin_router.put("/faults")
def set_faults(config: FaultConfig, request: Request) -> FaultConfig:
    state = FaultState(**config.model_dump())
    request.app.state.faults = state
    log.warning("fault injection updated", extra={"fields": config.model_dump()})
    return _publish(request, state)


@admin_router.delete("/faults")
def clear_faults(request: Request) -> FaultConfig:
    state = FaultState()
    request.app.state.faults = state
    log.warning("fault injection cleared")
    return _publish(request, state)
