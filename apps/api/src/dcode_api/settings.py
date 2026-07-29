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

    @property
    def cors_origins_list(self) -> list[str]:
        """Comma-separated CORS_ORIGINS env var → list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


api_settings = APISettings()
