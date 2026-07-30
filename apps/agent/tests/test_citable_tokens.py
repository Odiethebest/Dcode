"""The agent may not offer the model a citation the guardrail rejects by construction.

`groundedness._verify_symbol` matches `symbols.qualified_name` **exactly**, and the
indexer builds that name from the repository's directory layout — the recorded
`psf/requests` index stores `src.requests.api.get`, and 719 of its 724 symbols carry
that `src.` / `tests.` prefix with no short-form row anywhere. A model writing about
the library shortens the name, and the shortened form matches nothing.

So a qualified name in the 'Allowed citations' list is an instruction to produce a
reference that will be redacted. On the recorded 16-question run **not one
symbol-style citation survived** in any answer, while the four questions that lost
groundedness lost it to exactly 13 such references.

These tests pin the generation side only. They do not touch how groundedness is
computed: the API resolving a symbol by *suffix* match while this guardrail uses
*exact* match is a real asymmetry, and reconciling it would move the metric, so it
stays a separate decision.

**Mutation-verified, 3 reverts, all red** (assert on pytest's exit code, not on its
stdout):

    # 1 — re-add the symbol token in graph._allowed_citations:
    #       symbol = str(location["symbol"])
    #       if "." in symbol: add(symbol)
    #     → test_allowed_citations_offers_no_dotted_symbol_token,
    #       test_no_allowed_token_can_be_read_as_a_symbol_citation
    # 2 — re-backtick the name in graph._build_llm_context:
    #       f"- `{loc['symbol']}` at ..."
    #     → test_evidence_does_not_backtick_the_qualified_name
    # 3 — restore "`module.Class.method`" in llm.SYSTEM_PROMPT
    #     → test_prompt_never_presents_a_dotted_name_as_citable
    #
    # uv run pytest apps/agent/tests/test_citable_tokens.py -q; echo "exit=$?"
"""

from uuid import uuid4

from dcode_agent import graph
from dcode_agent.groundedness import SYMBOL_PATTERN, extract_citations
from dcode_agent.llm import SYSTEM_PROMPT
from dcode_agent.state import AgentState

# Neutral corpus coordinates on purpose — this repository's notes ask that the
# indexed library's credential-handling vocabulary stay out of the source tree's
# test fixtures, and nothing here needs it.
_QUALIFIED = "src.requests.api.get"
_SHORTENED = "requests.api.get"


def _state_with_definition_locations() -> AgentState:
    """A find_definition observation, the shape that used to add symbol tokens."""
    return AgentState(
        repo_id=str(uuid4()),
        query="where is the module-level request helper defined?",
        observations=[
            {
                "tool": "find_definition",
                "args": {"symbol": "get"},
                "result": {
                    "locations": [
                        {
                            "symbol": _QUALIFIED,
                            "file_path": "src/requests/api.py",
                            "line": 62,
                        }
                    ]
                },
                "cached": False,
            }
        ],
    )


def test_allowed_citations_offers_no_dotted_symbol_token() -> None:
    allowed = graph._allowed_citations(_state_with_definition_locations())

    assert "src/requests/api.py:62" in allowed, (
        "the location's file:line is the citable form and must still be offered"
    )
    assert _QUALIFIED not in allowed
    assert not [token for token in allowed if "." in token and ":" not in token], (
        f"a dotted token with no line is a qualified name: {allowed}"
    )


def test_no_allowed_token_can_be_read_as_a_symbol_citation() -> None:
    """The property that actually matters, stated over the extractor itself.

    Asserting "no dotted tokens" would only restate the change. This asserts the
    consequence: every offered token, written into an answer the way the prompt asks,
    is extracted as a `file:line` reference — never routed to the exact-match symbol
    path that cannot succeed here.
    """
    allowed = graph._allowed_citations(_state_with_definition_locations())
    assert allowed, "fixture produced no tokens, so the assertions below are vacuous"

    for token in allowed:
        rendered = f"see `{token}` for details"
        assert not SYMBOL_PATTERN.search(rendered), (
            f"allowed token {token!r} is extracted as a symbol citation, which "
            "verifies by exact match against a prefixed qualified name"
        )
        extracted = extract_citations(rendered)
        assert extracted, f"allowed token {token!r} is not extracted at all"
        assert all(line > 0 for _sym, _path, line in extracted), (
            f"allowed token {token!r} extracted without a line number"
        )


def test_evidence_does_not_backtick_the_qualified_name() -> None:
    """Backticked, the name in the evidence block is itself an invitation to cite it."""
    context = graph._build_llm_context(_state_with_definition_locations())

    assert _QUALIFIED in context, "the name is useful context and is not being dropped"
    assert f"`{_QUALIFIED}`" not in context
    assert "`src/requests/api.py:62`" in context, "the citable token stays backticked"


def test_prompt_never_presents_a_dotted_name_as_citable() -> None:
    """The prompt used to offer `module.Class.method` as an example citation form."""
    assert "`module.Class.method`" not in SYSTEM_PROMPT
    assert not SYMBOL_PATTERN.search(SYSTEM_PROMPT), (
        "a backticked dotted name anywhere in the prompt reads as a licensed form"
    )
    # And it says so positively, so the rule survives a rewrite of the examples.
    assert "dotted identifier in backticks" in SYSTEM_PROMPT


def test_the_shortened_form_is_what_a_model_would_write() -> None:
    """Pins the premise the whole change rests on, so it cannot rot silently.

    If the extractor ever stopped treating a bare dotted name as a citation, the
    reasoning above would no longer apply and this file should be revisited rather
    than trusted.
    """
    assert SYMBOL_PATTERN.search(f"`{_SHORTENED}`"), (
        "a backticked shortened name is extracted as a symbol citation — the "
        "premise for keeping qualified names out of the allowed list"
    )
    assert _SHORTENED != _QUALIFIED
    assert _QUALIFIED.endswith(f".{_SHORTENED.split('.', 1)[1]}")
