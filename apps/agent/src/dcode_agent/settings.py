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

    # --- Stream lifetime (Deploy.md R-2) ---
    # A query had no overall ceiling: /internal/query spawns a task and returns
    # a stream, and only the individual hops were bounded, so 14 steps x 30s
    # plus rerank and synthesis could run past eight minutes with nothing to
    # stop it. An abandoned request kept spending on three metered APIs with
    # nobody draining the queue.
    #
    # 240s is chosen to expire *inside* the hosting platform's 5-minute cut, so
    # the client gets a labelled `error` event instead of a connection that
    # simply stops. 0 disables the ceiling.
    request_budget_seconds: float = 240.0
    # Comment frames while the queue is quiet. Below both the platform's
    # 5-minute idle cut and the gateway client's 60s read timeout.
    sse_heartbeat_seconds: float = 20.0


agent_settings = AgentSettings()
