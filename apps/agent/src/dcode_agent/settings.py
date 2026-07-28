"""Agent service settings."""

from dcode_shared.settings import SharedSettings


class AgentSettings(SharedSettings):
    """Agent service configuration."""

    max_steps: int = 8  # DESIGN.md §2.3.1 single-query upper bound
    retrieval_base_url: str = "http://localhost:8000"  # TODO(M2): split-off retrieval service
    workdir_base: str = "/tmp/dcode-workdirs"

    # LLM answer synthesis (P1-4). Default 'stub' keeps rule-based templating;
    # set SYNTHESIS_MODEL to an OpenAI model + OPENAI_API_KEY to enable prose
    # answers grounded in the retrieved evidence (groundedness check unchanged).
    synthesis_model: str = "stub"
    openai_api_key: str = ""
    openai_base_url: str = ""
    synthesis_max_tokens: int = 700
    synthesis_temperature: float = 0.1


agent_settings = AgentSettings()
