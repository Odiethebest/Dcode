"""Agent service settings."""

from dcode_shared.settings import SharedSettings


class AgentSettings(SharedSettings):
    """Agent service configuration."""

    max_steps: int = 8  # DESIGN.md §2.3.1 single-query upper bound
    retrieval_base_url: str = "http://localhost:8000"  # TODO(M2): split-off retrieval service


agent_settings = AgentSettings()
