"""Shared helpers for internal-only service-to-service requests."""

INTERNAL_API_KEY_HEADER = "X-Dcode-Internal-Key"

# The settings default, repeated here so the guard below has something to
# compare against without importing settings into every caller.
PLACEHOLDER_INTERNAL_API_KEY = "__SET_LOCAL_DEV_INTERNAL_API_KEY__"

# Below this, a key is not a secret. Only enforced where the deployment looks
# like production — see `internal_api_key_error`.
_MIN_PRODUCTION_KEY_CHARS = 32


def internal_api_key_error(key: str, *, strict: bool) -> str | None:
    """Why this key cannot protect the internal surface, or None.

    Two rules, and they are deliberately different in strength.

    The placeholder is rejected **always**. It is published in this repository,
    so a service running on it has an internal retrieval and graph surface
    protected by a value anyone can read. `docker-compose.prod.yml` guards this
    with `${INTERNAL_API_KEY:?}`, but that only covers compose — a container
    started from the Dockerfile directly, which is what a platform like Railway
    does, has no such check.

    The length rule applies only when `strict`. Local development uses a short
    readable key on purpose and requiring 32 characters there would be noise
    with no reader. `strict` is passed as "this deployment authenticates its
    users", which is a proxy for production rather than a fact about it — an
    imperfect signal, chosen over having no rule at all outside compose.
    """
    stripped = key.strip()
    if not stripped:
        return "INTERNAL_API_KEY must be set"
    if stripped == PLACEHOLDER_INTERNAL_API_KEY:
        return (
            "INTERNAL_API_KEY is still the placeholder published in this repository. "
            "Set it to a real secret before starting."
        )
    if strict and len(stripped) < _MIN_PRODUCTION_KEY_CHARS:
        return (
            f"INTERNAL_API_KEY must be at least {_MIN_PRODUCTION_KEY_CHARS} characters "
            "when the deployment is gated"
        )
    return None


def internal_auth_headers(api_key: str) -> dict[str, str]:
    """Return the standard internal auth header for private routes."""
    return {INTERNAL_API_KEY_HEADER: api_key}
