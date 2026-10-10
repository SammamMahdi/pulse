import time

from fastapi.testclient import TestClient

from tests.conftest import ADMIN_TOKEN

AUTH = {"X-Admin-Token": ADMIN_TOKEN}


def test_admin_api_absent_when_disabled(client: TestClient) -> None:
    assert client.get("/admin/faults", headers=AUTH).status_code == 404


def test_admin_api_requires_token(fault_client: TestClient) -> None:
    assert fault_client.get("/admin/faults").status_code == 401
    assert (
        fault_client.get("/admin/faults", headers={"X-Admin-Token": "wrong-token-123456"}).status_code == 401
    )
    assert fault_client.get("/admin/faults", headers=AUTH).status_code == 200


def test_error_injection_returns_500_and_is_counted(fault_client: TestClient) -> None:
    fault_client.put("/admin/faults", json={"error_rate": 1.0}, headers=AUTH)
    assert fault_client.get("/api/v1/primes/10").status_code == 500
    # Ops endpoints are never affected by injected faults.
    assert fault_client.get("/health").status_code == 200
    metrics = fault_client.get("/metrics").text
    assert 'route="/api/v1/primes/{n}",status="500"} 1.0' in metrics
    assert "fault_injection_error_ratio 1.0" in metrics


def test_latency_injection_slows_api_requests(fault_client: TestClient) -> None:
    fault_client.put("/admin/faults", json={"latency_ms": 200}, headers=AUTH)
    start = time.perf_counter()
    assert fault_client.get("/api/v1/info").status_code == 200
    assert time.perf_counter() - start >= 0.2


def test_forced_not_ready_and_reset(fault_client: TestClient) -> None:
    fault_client.put("/admin/faults", json={"force_not_ready": True}, headers=AUTH)
    assert fault_client.get("/ready").status_code == 503
    assert fault_client.get("/health").status_code == 200  # liveness unaffected
    fault_client.delete("/admin/faults", headers=AUTH)
    assert fault_client.get("/ready").status_code == 200
    assert fault_client.get("/admin/faults", headers=AUTH).json()["error_rate"] == 0.0


def test_fault_config_is_validated(fault_client: TestClient) -> None:
    assert fault_client.put("/admin/faults", json={"error_rate": 1.5}, headers=AUTH).status_code == 422
    assert fault_client.put("/admin/faults", json={"latency_ms": -5}, headers=AUTH).status_code == 422
