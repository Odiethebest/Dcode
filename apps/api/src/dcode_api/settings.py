"""API gateway settings — extends SharedSettings with gateway-specific knobs."""

from dcode_shared.settings import SharedSettings


class APISettings(SharedSettings):
    """API gateway configuration."""

    cors_origins: str = "http://localhost:5173"
    agent_url: str = "http://localhost:8001"

    @property
    def cors_origins_list(self) -> list[str]:
        """Comma-separated CORS_ORIGINS env var → list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


api_settings = APISettings()
