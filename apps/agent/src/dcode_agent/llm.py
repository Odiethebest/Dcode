"""Optional LLM answer-synthesis and follow-up contextualization client.

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
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = logging.getLogger("dcode.agent.llm")

_DEFAULT_MAX_TOKENS = 700
_DEFAULT_TEMPERATURE = 0.1
_DEFAULT_TIMEOUT_SECONDS = 60.0

ResponseLanguage = Literal["Chinese", "English"]

SYSTEM_PROMPT = (
    "You are Dcode, a code-understanding assistant. Answer the developer's "
    "question about a codebase using ONLY the retrieved code evidence provided. "
    "Be concise and concrete, and explain how the pieces fit together.\n\n"
    "Language and formatting rules:\n"
    "- Answer in the same natural language as the developer's current question. "
    "A Chinese question must receive a Chinese answer; an English question must "
    "receive an English answer.\n"
    "- Do not let the language of source code, comments, retrieved evidence, or "
    "conversation history override the current question's language. Keep code "
    "identifiers and citation tokens verbatim.\n"
    "- Write inline math as `$...$` and display math as `$$...$$`. Do not use "
    "`\\(...\\)` or `\\[...\\]` delimiters. Keep the TeX valid for KaTeX; for "
    "example, escape a literal underscore inside `\\text{...}` as `\\_`.\n\n"
    "Citation rules (mandatory — every citation is machine-verified against the "
    "index; an evidence ID that is not in the server-provided catalog is stripped "
    "and lowers the answer's groundedness score below the acceptance bar):\n"
    "- Cite ONLY evidence IDs copied verbatim from the 'Evidence catalog' at the "
    "end of the evidence, for example [C1] or [C2].\n"
    "- Keep evidence IDs outside backticks. Backticks are only code formatting: "
    "ordinary identifiers such as `self.client.retrieve` are not citations.\n"
    "- Do NOT invent an evidence ID or use a file, line, or symbol as a substitute "
    "citation, even if you recognise it from general knowledge or infer it from code.\n"
    "- Attach an evidence ID to each concrete claim.\n"
    "- If the evidence catalog is insufficient to answer, say so plainly.\n\n"
    "Call-graph honesty rule:\n"
    "- Callers/callees listed by the call-graph tool are resolved static edges. "
    "A call expression visible only in a source excerpt is not a resolved target; "
    "describe it explicitly as a source-level unresolved call.\n"
    "- When the question asks what a symbol calls, include every source-level call "
    "expression returned by the tool. If any is marked UNRESOLVED, do not claim "
    "that the resolved callee list is exhaustive."
)

_CONTEXTUALIZE_MAX_TOKENS = 128
_CONTEXTUALIZE_SYSTEM_PROMPT = (
    "You rewrite a developer's follow-up question about a codebase into a "
    "standalone question answerable without the prior conversation. Resolve "
    'references ("it", "that function", "the same file") using the conversation, '
    "keep it a single question, preserve exact code symbols verbatim, and add no "
    "new facts. Keep the standalone question in the same natural language as the "
    "follow-up; do not translate it. If the follow-up is already standalone, "
    "return it unchanged."
)


def response_language_for(question: str) -> ResponseLanguage:
    """Choose the answer language from the current user's wording.

    Code identifiers are predominantly Latin even inside Chinese questions, so
    the presence of a Han character is the reliable signal for this product's
    Chinese/English language contract. Symbol-only questions default to English.
    """
    has_han = any(
        "\u3400" <= char <= "\u4dbf" or "\u4e00" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff"
        for char in question
    )
    return "Chinese" if has_han else "English"


def _build_synthesis_messages(
    *, question: str, context: str, response_language: ResponseLanguage
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Required answer language: {response_language}. This is mandatory "
                "and was determined from the developer's current question.\n\n"
                f"Question:\n{question}\n\nRetrieved evidence:\n{context}"
            ),
        },
    ]


class LLMClient(ABC):
    """Abstract answer-synthesis LLM used by the agent's synthesize node."""

    @abstractmethod
    def stream(
        self,
        *,
        question: str,
        context: str,
        response_language: ResponseLanguage,
    ) -> AsyncIterator[str]:
        """Yield answer-text deltas as the model generates them."""

    async def contextualize(self, *, question: str, history: list[dict[str, str]]) -> str | None:
        """Rewrite a follow-up into a standalone query using prior turns.

        Default: no rewrite (returns ``None``) so single-turn and template paths
        are unaffected; real clients override. This feeds retrieval + planning
        only — the groundedness guardrail is untouched, so history can never
        introduce an unverifiable citation.
        """
        return None


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

    async def stream(
        self,
        *,
        question: str,
        context: str,
        response_language: ResponseLanguage,
    ) -> AsyncIterator[str]:
        messages: Any = _build_synthesis_messages(
            question=question,
            context=context,
            response_language=response_language,
        )
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            stream=True,
        )
        async for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def contextualize(self, *, question: str, history: list[dict[str, str]]) -> str | None:
        if not history:
            return None
        transcript = "\n".join(
            f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history
        )
        messages: Any = [
            {"role": "system", "content": _CONTEXTUALIZE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Conversation so far:\n{transcript}\n\n"
                    f"Follow-up question:\n{question}\n\nStandalone question:"
                ),
            },
        ]
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=_CONTEXTUALIZE_MAX_TOKENS,
            temperature=0.0,
            stream=False,
        )
        if not completion.choices:
            return None
        content = completion.choices[0].message.content
        return content.strip() if content else None


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
