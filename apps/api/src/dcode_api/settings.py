"""API gateway settings — extends SharedSettings with gateway-specific knobs."""

from dcode_shared.settings import SharedSettings


class APISettings(SharedSettings):
    """API gateway configuration."""

    cors_origins: str = "http://localhost:5173"
    agent_url: str = "http://localhost:8001"
    index_queue_name: str = "dcode.index_jobs"

    # Multi-turn history bounds — enforced on the /query path before the turns
    # reach the planner, the proxied agent body, or the cache key.
    query_history_max_turns: int = 6
    query_history_max_chars: int = 2000
    query_history_max_turn_chars: int = 4000

    # --- Single shared-account gate (Deploy.md D-6) ---
    # Off by default so local development, the test suite and every current
    # compose invocation are unaffected. docker-compose.prod.yml hardcodes it
    # on, and a config-hardening test pins that, so a deployment cannot forget.
    # When on but unconfigured the app refuses to start: an auth gate that
    # fails open is worse than none, because it looks like one.
    auth_enabled: bool = False
    auth_username: str = "dcode"
    auth_password_hash: str = ""
    auth_session_secret: str = ""
    auth_session_ttl_seconds: int = 12 * 60 * 60
    # Browsers treat http://localhost as a trustworthy origin, so a Secure
    # cookie still works there; this exists for a plain-HTTP staging host.
    auth_cookie_secure: bool = True
    # The login wall stops anonymous callers. It does not stop a signed-in one
    # looping a query against three metered APIs, which is what this bounds.
    auth_daily_query_limit: int = 200

    # /docs, /redoc and /openapi.json advertise the /internal/* surface.
    # Useful locally, so on by default; prod compose turns it off.
    docs_enabled: bool = True

    # Comma-separated clone-target allowlist. Empty means any public host, which
    # is what a demo indexing arbitrary open-source repositories needs. Set it
    # and it becomes the only rule in the URL check that states what is
    # *allowed* rather than what is obviously wrong. Subdomains match.
    repo_url_allowed_hosts: str = ""

    @property
    def repo_url_allowed_hosts_list(self) -> list[str]:
        """Comma-separated REPO_URL_ALLOWED_HOSTS env var → lowercased list."""
        return [h.strip().lower() for h in self.repo_url_allowed_hosts.split(",") if h.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """Comma-separated CORS_ORIGINS env var → list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


api_settings = APISettings()
