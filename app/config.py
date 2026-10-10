"""Runtime configuration loaded from environment variables (12-factor style).

Invalid values raise ConfigError at startup so a misconfigured container fails
fast and visibly instead of serving traffic with surprising behaviour.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_MIN_TOKEN_LENGTH = 16


class ConfigError(ValueError):
    """Raised when an environment variable holds an invalid value."""


def _parse_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{key} must be true or false, got {raw!r}")


def _parse_int(env: Mapping[str, str], key: str, default: int, low: int, high: int) -> int:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from None
    if not low <= value <= high:
        raise ConfigError(f"{key} must be between {low} and {high}, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    service_name: str
    version: str
    environment: str
    log_level: str
    max_prime_limit: int
    fault_injection_enabled: bool
    admin_token: str | None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        log_level = env.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in _LOG_LEVELS:
            raise ConfigError(f"LOG_LEVEL must be one of {sorted(_LOG_LEVELS)}, got {log_level!r}")

        fault_injection = _parse_bool(env, "FAULT_INJECTION_ENABLED", default=False)
        admin_token = env.get("ADMIN_TOKEN") or None
        if fault_injection and admin_token is None:
            raise ConfigError("ADMIN_TOKEN is required when FAULT_INJECTION_ENABLED=true")
        if admin_token is not None and len(admin_token) < _MIN_TOKEN_LENGTH:
            raise ConfigError(f"ADMIN_TOKEN must be at least {_MIN_TOKEN_LENGTH} characters")

        return cls(
            service_name=env.get("SERVICE_NAME", "pulse-api"),
            version=env.get("APP_VERSION", "0.0.0-dev"),
            environment=env.get("APP_ENV", "local"),
            log_level=log_level,
            max_prime_limit=_parse_int(env, "MAX_PRIME_LIMIT", 1_000_000, 1, 10_000_000),
            fault_injection_enabled=fault_injection,
            admin_token=admin_token,
        )
