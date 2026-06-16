"""Shared helpers for internal-only service-to-service requests."""

INTERNAL_API_KEY_HEADER = "X-Dcode-Internal-Key"


def internal_auth_headers(api_key: str) -> dict[str, str]:
    """Return the standard internal auth header for private routes."""
    return {INTERNAL_API_KEY_HEADER: api_key}
