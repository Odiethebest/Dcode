"""Eval harness settings."""

from dcode_shared.settings import SharedSettings


class EvalSettings(SharedSettings):
    api_base_url: str = "http://localhost:8000"
    agent_base_url: str = "http://localhost:8001"
    retrieval_k: int = 5


eval_settings = EvalSettings()
