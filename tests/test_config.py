import pytest

from app.config import ConfigError, Settings


def test_defaults_are_safe() -> None:
    settings = Settings.from_env({})
    assert settings.fault_injection_enabled is False
    assert settings.admin_token is None
    assert settings.log_level == "INFO"
    assert settings.max_prime_limit == 1_000_000


def test_values_are_read_from_environment() -> None:
    settings = Settings.from_env(
        {
            "APP_VERSION": "2.0.0",
            "APP_ENV": "staging",
            "LOG_LEVEL": "debug",
            "MAX_PRIME_LIMIT": "500",
        }
    )
    assert (settings.version, settings.environment, settings.log_level, settings.max_prime_limit) == (
        "2.0.0",
        "staging",
        "DEBUG",
        500,
    )


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"MAX_PRIME_LIMIT": "lots"}, "must be an integer"),
        ({"MAX_PRIME_LIMIT": "0"}, "between"),
        ({"LOG_LEVEL": "LOUD"}, "LOG_LEVEL"),
        ({"FAULT_INJECTION_ENABLED": "maybe"}, "true or false"),
        ({"FAULT_INJECTION_ENABLED": "true"}, "ADMIN_TOKEN is required"),
        ({"ADMIN_TOKEN": "short"}, "at least 16"),
    ],
)
def test_invalid_configuration_fails_fast(env: dict[str, str], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        Settings.from_env(env)
