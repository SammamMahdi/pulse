from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ADMIN_TOKEN = "test-admin-token-0123456789"  # noqa: S105 - fixture value, not a real credential


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "service_name": "pulse-api",
        "version": "1.2.3-test",
        "environment": "test",
        "log_level": "INFO",
        "max_prime_limit": 1000,
        "fault_injection_enabled": False,
        "admin_token": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client


@pytest.fixture
def fault_client() -> Iterator[TestClient]:
    settings = make_settings(fault_injection_enabled=True, admin_token=ADMIN_TOKEN)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
