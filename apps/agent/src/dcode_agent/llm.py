"""LLM answer-synthesis client for the agent (P1-4).

The agent's default synthesis is rule-based templating. When a synthesis model
is configured (``SYNTHESIS_MODEL`` != ``stub`` with an ``OPENAI_API_KEY``), the
synthesize node instead asks an LLM to write a grounded, citation-formatted
answer from the retrieved evidence. Groundedness verification runs unchanged
afterwards, so any citation the model emits is still checked against the index
and unverified references are stripped.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = logging.getLogger("dcode.agent.llm")

_DEFAULT_MAX_TOKENS = 700
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_TIMEOUT_SECONDS = 60.0

SYSTEM_PROMPT = (
    "You are Dcode, a code-understanding assistant. Answer the developer's "
    "question about a codebase using ONLY the retrieved code evidence provided. "
    "Be concise and concrete, and explain how the pieces fit together.\n\n"
    "Citation rules (mandatory — every citation is machine-verified against the "
    "index, and any unverified citation is stripped and lowers the answer's "
    "groundedness score):\n"
    "- Cite each code location inline as a backticked `path/to/file.py:LINE`, "
    "using the exact path and line from the evidence.\n"
    "- Cite symbols as backticked dotted qualified names, e.g. "
    "`module.Class.method`.\n"
    "- Never invent files, lines, or symbols that are not in the evidence.\n"
    "- If the evidence is insufficient to answer, say so plainly."
)


class LLMClient(ABC):
    """Abstract answer-synthesis LLM used by the agent's synthesize node."""

    @abstractmethod
    async def synthesize(self, *, question: str, context: str) -> str:
        """Return a grounded natural-language answer for the question."""


class OpenAILLMClient(LLMClient):
    """Answer synthesis via the OpenAI Chat Completions API."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = "",
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        temperature: float = _DEFAULT_TEMPERATURE,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        from openai import AsyncOpenAI

        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        # An empty OPENAI_BASE_URL (compose passes it through as "") would
        # otherwise poison the SDK into building a scheme-less URL, so fall back
        # to the public OpenAI endpoint explicitly instead of passing "".
        self._client: AsyncOpenAI = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.strip() or "https://api.openai.com/v1",
            timeout=timeout_seconds,
        )

    async def synthesize(self, *, question: str, context: str) -> str:
        messages: Any = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nRetrieved evidence:\n{context}",
            },
        ]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        content = response.choices[0].message.content
        if content is None or not content.strip():
            raise RuntimeError("LLM returned an empty completion")
        return content.strip()


def create_llm_client(
    *,
    model: str,
    api_key: str,
    base_url: str = "",
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = _DEFAULT_TEMPERATURE,
) -> LLMClient | None:
    """Build the synthesis LLM client, or ``None`` to keep template synthesis.

    Returns ``None`` when ``model`` is ``stub`` so the agent keeps its rule-based
    answer path. Raises when a real model is selected without an API key so the
    misconfiguration surfaces at startup instead of silently degrading.
    """
    if model == "stub":
        return None
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY is required when SYNTHESIS_MODEL is not 'stub'")
    logger.info("using OpenAI synthesis client model=%s", model)
    return OpenAILLMClient(
        model=model,
        api_key=api_key,
        base_url=base_url,
        max_tokens=max_tokens,
        temperature=temperature,
    )
