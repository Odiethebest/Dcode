"""Agent service settings."""

from dcode_shared.settings import SharedSettings


class AgentSettings(SharedSettings):
    """Agent service configuration."""

    max_steps: int = 8  # single-query tool-step upper bound
    retrieval_base_url: str = "http://localhost:8000"  # API gateway internal retrieval surface
    workdir_base: str = "/tmp/dcode-workdirs"

    # Optional LLM answer synthesis. Default 'stub' keeps rule-based templating;
    # set SYNTHESIS_MODEL to an OpenAI model + OPENAI_API_KEY to enable prose
    # answers grounded in the retrieved evidence (groundedness check unchanged).
    synthesis_model: str = "stub"
    openai_api_key: str = ""
    openai_base_url: str = ""
    synthesis_max_tokens: int = 700
    synthesis_temperature: float = 0.1


agent_settings = AgentSettings()
