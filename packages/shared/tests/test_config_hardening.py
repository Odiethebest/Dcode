"""Configuration hardening checks for env examples and compose files."""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]

# A compose service block: `  name:` at two spaces, everything under it deeper.
# Parsed by hand rather than with PyYAML, which is only a transitive dependency
# here and is imported by no other code in this repository.
_SERVICE_HEADER = re.compile(r"^ {2}([a-z0-9_-]+):\s*$")


def _service_block(compose_text: str, service: str) -> str:
    lines = compose_text.splitlines()
    starts = [i for i, line in enumerate(lines) if _SERVICE_HEADER.match(line)]
    for position, index in enumerate(starts):
        match = _SERVICE_HEADER.match(lines[index])
        assert match is not None
        if match.group(1) != service:
            continue
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        return "\n".join(lines[index:end])
    raise AssertionError(f"service {service!r} not found in compose file")


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


def test_prod_compose_requires_an_explicit_embedding_dimension() -> None:
    """A defaulted EMBEDDING_DIM in production is not a slow query, it is a re-index.

    The migration sizes the pgvector column from this value
    (infra/migrations/versions/001_initial_schema.py) and the ORM binds the
    column type to it at import time (dcode_shared.db.models). Once the volume
    exists the dimension cannot change, so production must state it rather than
    inherit the 1024 code default that happens to suit stub vectors.
    """
    compose = (_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "${EMBEDDING_DIM:-" not in compose
    assert "${EMBEDDING_DIM:?" in compose


def test_prod_services_receive_the_retrieval_settings_they_read() -> None:
    """Every service must be able to receive each setting it actually reads.

    Violating this produces no error and no log line. The API embeds the search
    query and the worker embeds the corpus; if only one of them is configured,
    real vectors get searched with a stub all-zero query vector and dense
    retrieval silently returns noise. The production API shipped with none of
    these, which also meant `make prod-migrate` built the column at the default
    dimension no matter what the env file said.

    The expected sets below are what each service reads today. If a service
    starts reading a new setting, add it here as well as to the compose file.
    """
    compose = (_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    expected = {
        # dcode_api.routes.internal builds both the query embedding client and
        # the query reranker client, and fuses with the RRF weights.
        "api": {
            "EMBEDDING_MODEL",
            "EMBEDDING_DIM",
            "EMBEDDING_ENDPOINT",
            "EMBEDDING_BATCH_SIZE",
            "EMBEDDING_MAX_RETRIES",
            "EMBEDDING_TIMEOUT_SECONDS",
            "RRF_DENSE_WEIGHT",
            "RRF_SPARSE_WEIGHT",
            "RERANKER_MODEL",
            "RERANKER_ENDPOINT",
            "RERANKER_CANDIDATE_LIMIT",
            "RERANKER_MAX_RETRIES",
        },
        # dcode_worker.stages.embed builds the index-time embedding client.
        "worker": {
            "EMBEDDING_MODEL",
            "EMBEDDING_DIM",
            "EMBEDDING_ENDPOINT",
            "EMBEDDING_BATCH_SIZE",
            "EMBEDDING_MAX_RETRIES",
            "EMBEDDING_TIMEOUT_SECONDS",
        },
        # dcode_agent.graph reranks its own evidence union; EMBEDDING_DIM is
        # not read by the agent directly but binds the ORM column type.
        "agent": {
            "EMBEDDING_DIM",
            "RERANKER_MODEL",
            "RERANKER_ENDPOINT",
            "RERANKER_MAX_RETRIES",
            "SYNTHESIS_MODEL",
            "SYNTHESIS_MAX_TOKENS",
            "SYNTHESIS_TEMPERATURE",
            "GROUNDEDNESS_THRESHOLD",
        },
    }

    for service, variables in expected.items():
        block = _service_block(compose, service)
        missing = sorted(name for name in variables if f"\n      {name}:" not in block)
        assert not missing, f"{service} is missing {missing} in docker-compose.prod.yml"


def test_no_dead_loopback_endpoints_in_production_config() -> None:
    """A reranker endpoint pointing at localhost:9999 inside a container.

    It resolved to nothing, and because RERANKER_MODEL defaulted to stub the
    client was never built, so the dead address never produced an error either.
    An empty endpoint is the honest default: a real model with no endpoint
    raises at construction, and a stub model ignores it.
    """
    compose = (_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    env_prod_example = (_ROOT / ".env.production.example").read_text(encoding="utf-8")

    for content in (compose, env_prod_example):
        assert "localhost:9999" not in content
