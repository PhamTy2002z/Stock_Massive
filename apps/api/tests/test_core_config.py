"""AUTH_SECRET validation: a guessable signing key never reaches a real deployment."""
import logging

import pytest
from pydantic import ValidationError

from src.core.config import Settings

STRONG = "q2Vt3yJ8sX0c9LkP4mN7bR1dF6gH5jKa"  # 32 bytes


@pytest.mark.parametrize(
    "secret",
    [
        "dev-secret-change-in-production",
        "generate-with-openssl-rand-base64-32",
        "change-me",
        "CHANGE-ME",
        "",
        "   ",
        "a" * 31,
    ],
)
@pytest.mark.parametrize("environment", ["production", "staging", "prod"])
def test_a_weak_secret_is_refused_outside_development(secret, environment):
    with pytest.raises(ValidationError, match="AUTH_SECRET"):
        Settings(auth_secret=secret, environment=environment)


def test_a_strong_secret_is_accepted_in_production():
    settings = Settings(auth_secret=STRONG, environment="production")
    assert settings.auth_secret == STRONG


@pytest.mark.parametrize("environment", ["development", "test", "Development"])
def test_development_keeps_working_with_a_warning(environment, caplog):
    with caplog.at_level(logging.WARNING, logger="src.core.config"):
        settings = Settings(
            auth_secret="dev-secret-change-in-production", environment=environment
        )
    assert settings.auth_secret == "dev-secret-change-in-production"
    assert "AUTH_SECRET" in caplog.text


def test_the_default_is_production(monkeypatch):
    """A deployment that never names its environment gets the strict checks."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = Settings(_env_file=None, auth_secret=STRONG)
    assert settings.environment == "production"
    assert settings.is_development is False


def test_a_weak_secret_with_no_environment_named_points_at_the_local_fix(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(ValidationError, match="set ENVIRONMENT=development"):
        Settings(_env_file=None, auth_secret="change-me")


def test_the_suite_runs_as_a_test_environment():
    """``conftest.py`` names it before anything reads the settings."""
    assert Settings().is_development is True
