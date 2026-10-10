from fastapi.testclient import TestClient


def _metric_lines(client: TestClient, name: str) -> list[str]:
    body = client.get("/metrics").text
    return [line for line in body.splitlines() if line.startswith(name)]


def test_metrics_endpoint_exposes_prometheus_format(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# TYPE http_requests_total counter" in response.text
    assert 'app_info{environment="test",version="1.2.3-test"} 1.0' in response.text


def test_requests_are_labelled_by_route_template_not_raw_path(client: TestClient) -> None:
    for n in (5, 50, 500):
        client.get(f"/api/v1/primes/{n}")
    lines = _metric_lines(client, "http_requests_total{")
    route_line = [line for line in lines if 'route="/api/v1/primes/{n}"' in line and 'status="200"' in line]
    assert route_line and route_line[0].endswith(" 3.0")
    assert not any("/api/v1/primes/5" in line for line in lines)


def test_unknown_paths_share_one_label(client: TestClient) -> None:
    client.get("/does-not-exist")
    client.get("/also/missing")
    lines = _metric_lines(client, "http_requests_total{")
    assert any(
        'route="<unmatched>"' in line and 'status="404"' in line and line.endswith(" 2.0") for line in lines
    )


def test_latency_histogram_is_recorded(client: TestClient) -> None:
    client.get("/api/v1/info")
    lines = _metric_lines(client, "http_request_duration_seconds_count{")
    assert any('route="/api/v1/info"' in line and line.endswith(" 1.0") for line in lines)


def test_ready_gauge_reflects_lifecycle(client: TestClient) -> None:
    assert "app_ready 1.0" in client.get("/metrics").text
