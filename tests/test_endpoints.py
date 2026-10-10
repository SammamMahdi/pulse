import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import count_primes, create_app
from app.observability import JsonFormatter
from tests.conftest import make_settings


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_after_startup(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_not_ready_before_startup() -> None:
    # Without the context manager the lifespan (startup) never runs.
    response = TestClient(create_app(make_settings())).get("/ready")
    assert response.status_code == 503


def test_info_reports_version_and_environment(client: TestClient) -> None:
    body = client.get("/api/v1/info").json()
    assert body["version"] == "1.2.3-test"
    assert body["environment"] == "test"
    assert body["hostname"]


@pytest.mark.parametrize(
    ("n", "count", "largest"),
    [(0, 0, None), (1, 0, None), (2, 1, 2), (10, 4, 7), (100, 25, 97), (1000, 168, 997)],
)
def test_primes_endpoint(client: TestClient, n: int, count: int, largest: int | None) -> None:
    response = client.get(f"/api/v1/primes/{n}")
    assert response.status_code == 200
    assert response.json() == {"n": n, "prime_count": count, "largest_prime": largest}


@pytest.mark.parametrize("bad", ["-1", "abc", "1.5"])
def test_primes_rejects_invalid_input(client: TestClient, bad: str) -> None:
    assert client.get(f"/api/v1/primes/{bad}").status_code == 422


def test_primes_rejects_values_above_limit(client: TestClient) -> None:
    response = client.get("/api/v1/primes/1001")
    assert response.status_code == 422
    assert "1000" in response.json()["detail"]


def test_count_primes_matches_known_value() -> None:
    assert count_primes(1_000_000) == (78_498, 999_983)


def test_request_id_is_propagated_or_generated(client: TestClient) -> None:
    assert client.get("/health", headers={"X-Request-ID": "abc123"}).headers["X-Request-ID"] == "abc123"
    assert len(client.get("/health").headers["X-Request-ID"]) == 32


def test_access_log_is_structured_json(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="pulse"):
        client.get("/api/v1/primes/10", headers={"X-Request-ID": "trace-me"})
    record = next(r for r in caplog.records if getattr(r, "fields", {}).get("request_id") == "trace-me")
    entry = json.loads(JsonFormatter().format(record))
    assert entry["msg"] == "request"
    assert entry["route"] == "/api/v1/primes/{n}"
    assert entry["status"] == 200
    assert entry["level"] == "INFO"
    assert entry["duration_ms"] >= 0


def test_probe_requests_are_logged_at_debug(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="pulse"):
        client.get("/health")
    record = next(r for r in caplog.records if r.getMessage() == "request")
    assert record.levelno == logging.DEBUG
