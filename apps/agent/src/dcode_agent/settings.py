"""Agent service settings."""

from dcode_shared.settings import SharedSettings


class AgentSettings(SharedSettings):
    """Agent service configuration."""

    # Single-query tool-step upper bound. Raised from 8 because B4's expansion
    # saturated it: 1 search + 3 read_file + 3 find_references left exactly one
    # step for get_file_outline, while the no-graph arm reached two outlines on
    # the same budget. The walk was ending at the cap rather than at the
    # planner's decision, which is a truncation artefact, not a policy.
    max_steps: int = 14
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
