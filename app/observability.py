"""Prometheus metrics and structured JSON logging."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from app.config import Settings

# Buckets cover fast health checks (ms) up to slow, fault-injected requests (s).
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class Metrics:
    """All application metrics, registered on a per-app registry (keeps tests isolated)."""

    def __init__(self, settings: Settings, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.requests = Counter(
            "http_requests_total",
            "HTTP requests processed, labelled by route template (not raw path).",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.latency = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds.",
            ["method", "route"],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )
        self.in_progress = Gauge(
            "http_requests_in_progress", "HTTP requests currently being served.", registry=self.registry
        )
        self.ready = Gauge("app_ready", "1 when this instance reports ready.", registry=self.registry)
        self.info = Gauge(
            "app_info",
            "Build information (value is always 1).",
            ["version", "environment"],
            registry=self.registry,
        )
        self.info.labels(settings.version, settings.environment).set(1)
        self.fault_latency = Gauge(
            "fault_injection_latency_seconds",
            "Injected latency per /api request (lab only).",
            registry=self.registry,
        )
        self.fault_error_ratio = Gauge(
            "fault_injection_error_ratio",
            "Injected error probability for /api requests (lab only).",
            registry=self.registry,
        )


class JsonFormatter(logging.Formatter):
    """One JSON object per line; extra structured fields go in record.fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Route uvicorn's server logs through the JSON handler; we emit our own access logs.
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
