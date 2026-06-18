"""Configuration hardening checks for env examples and compose files."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


def test_env_examples_do_not_ship_known_weak_credentials() -> None:
    env_example = (_ROOT / ".env.example").read_text(encoding="utf-8")
    env_prod_example = (_ROOT / ".env.production.example").read_text(encoding="utf-8")

    for content in (env_example, env_prod_example):
        assert "dev-internal-key-change-me" not in content
        assert "guest:guest" not in content
        assert "POSTGRES_PASSWORD=dcode" not in content
        assert "POSTGRES_PASSWORD=change-me" not in content


def test_prod_compose_requires_explicit_secret_env_vars() -> None:
    compose = (_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "${POSTGRES_PASSWORD:-" not in compose
    assert "${RABBITMQ_PASSWORD:-" not in compose
    assert "${INTERNAL_API_KEY:-" not in compose
    assert "guest:guest" not in compose
    assert "${POSTGRES_PASSWORD:?" in compose
    assert "${RABBITMQ_PASSWORD:?" in compose
    assert "${INTERNAL_API_KEY:?" in compose
