"""Server-owned evidence targets must survive groundedness verification.

LLM synthesis cites request-local IDs such as ``[C1]`` rather than copying a
qualified symbol into backticks. The server maps each ID back to a canonical
target, then applies the same symbol-resolution rule as the graph API. These
tests pin both sides of that contract: target resolution remains shared, and
the generated context exposes only IDs as citations.

**Mutation-verified, 5 reverts, all red** — over this file *and*
`test_groundedness.py`, because mutation 5 survives this file alone. The first run
reported 4 of 5 killed: the identity assertion below proves the shared rule is
*imported*, and nothing here proved it was *used*. Reverting `_verify_symbol` left
every test in this file green. `test_verify_accepts_a_symbol_written_without_the_indexed_prefix`
was written for exactly that gap, which is the whole reason this project runs the
mutation rather than trusting the docstring.

Run both files, and read the exit code, not the output:

    # 1 — `select_symbol_matches` returns only exact matches
    #     → test_the_shortened_form_a_model_writes_now_resolves
    #       test_every_allowed_symbol_token_resolves_against_its_own_row
    # 2 — drop the leading dot: endswith(symbol) instead of endswith("." + symbol)
    #     → test_a_suffix_must_fall_on_a_component_boundary
    # 3 — exact matches merged with suffix matches instead of winning outright
    #     → test_an_exact_match_wins_outright
    # 4 — autoescape=False in candidate_filter
    #     → test_underscore_is_escaped_and_not_a_sql_wildcard
    # 5 — `_verify_symbol` back to `qualified_name == symbol`
    #     → test_groundedness.py::test_verify_accepts_a_symbol_written_without_the_indexed_prefix
    #       (NOT caught by anything in this file — see above)
    #
    # uv run pytest apps/agent/tests/test_citable_tokens.py \
    #               apps/agent/tests/test_groundedness.py -q; echo "exit=$?"
"""

from dataclasses import dataclass
from uuid import uuid4

from dcode_agent import graph
from dcode_agent.groundedness import extract_citations
from dcode_agent.state import AgentState
from dcode_shared.db.models import Symbol
from dcode_shared.symbols import candidate_filter, select_symbol_matches

# Neutral corpus coordinates: this repository's notes ask that the indexed
# library's credential-handling vocabulary stay out of test fixtures.
INDEXED = "src.requests.api.get"
SHORTENED = "requests.api.get"


@dataclass
class Row:
    """Stands in for a `symbols` row — the rule only reads `qualified_name`."""

    qualified_name: str


def _state_with_definition_locations() -> AgentState:
    return AgentState(
        repo_id=str(uuid4()),
        query="where is the module-level request helper defined?",
        observations=[
            {
                "tool": "find_definition",
                "args": {"symbol": "get"},
                "result": {
                    "locations": [
                        {"symbol": INDEXED, "file_path": "src/requests/api.py", "line": 62}
                    ]
                },
                "cached": False,
            }
        ],
    )


def test_the_shortened_form_a_model_writes_now_resolves() -> None:
    """The defect this change fixes, stated as the smallest case that shows it."""
    rows = [Row(INDEXED)]

    assert select_symbol_matches(rows, INDEXED), "an exact name must still resolve"
    assert select_symbol_matches(rows, SHORTENED), (
        f"{SHORTENED!r} is how the name is written outside this repository's layout; "
        "rejecting it is what made the guardrail disagree with the find-definition tool"
    )
    assert select_symbol_matches(rows, "api.get")


def test_every_allowed_symbol_token_resolves_against_its_own_row() -> None:
    """The invariant, over the tokens the agent actually offers.

    Asserting "no dotted tokens" would only restate whichever remedy is in force.
    This asserts the property both remedies exist to produce: nothing in the list is
    a reference the guardrail's rule cannot accept.
    """
    allowed = graph._allowed_citations(_state_with_definition_locations())
    assert allowed, "fixture produced no tokens, so the assertions below are vacuous"

    symbol_tokens = [t for t in allowed if "." in t and ":" not in t]
    file_line_tokens = [t for t in allowed if ":" in t]
    assert file_line_tokens, "the location's file:line must still be offered"

    for token in symbol_tokens:
        assert select_symbol_matches([Row(token)], token), (
            f"allowed token {token!r} does not resolve under the guardrail's own rule"
        )
    for token in file_line_tokens:
        extracted = extract_citations(f"see `{token}`")
        assert extracted and all(line > 0 for _s, _p, line in extracted), (
            f"allowed token {token!r} is not extracted as a file:line reference"
        )


def test_an_exact_match_wins_outright() -> None:
    """Not merged with suffix matches.

    A name that fully identifies a row is unambiguous. Merging would make one
    citation resolve to every `*.api.get` in the corpus whenever an exact row also
    existed, and the guardrail would then be reporting on a set the model never named.
    """
    rows = [Row("api.get"), Row("src.requests.api.get"), Row("other.pkg.api.get")]
    matches = select_symbol_matches(rows, "api.get")

    assert [m.qualified_name for m in matches] == ["api.get"]


def test_a_suffix_must_fall_on_a_component_boundary() -> None:
    """The leading dot is load-bearing, not decoration."""
    assert not select_symbol_matches([Row("src.requests.widget")], "get")
    assert not select_symbol_matches([Row("src.legacy_api.get")], "api.get")
    assert select_symbol_matches([Row("src.legacy.api.get")], "api.get")


def test_underscore_is_escaped_and_not_a_sql_wildcard() -> None:
    """`_` matches any single character in LIKE, and Python names are full of them.

    Unescaped, a citation of `api._get` would also be satisfied by `api.aget`. That
    is a silent false positive inside a guardrail, so the SQL narrowing has to
    escape — asserted on the compiled statement rather than on a live database, so
    it runs with no infrastructure.
    """
    compiled = str(
        candidate_filter(Symbol.qualified_name, "api._get").compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "ESCAPE" in compiled.upper(), f"no ESCAPE clause in: {compiled}"
    # And the Python authority has no wildcard semantics at all.
    assert not select_symbol_matches([Row("src.api.aget")], "api._get")
    assert select_symbol_matches([Row("src.api._get")], "api._get")


def test_the_guardrail_and_the_api_share_one_rule() -> None:
    """Not two implementations that happen to agree today.

    Checked by identity of the imported object, not by comparing behaviour: two
    copies can agree on every case anyone thought to test and diverge on the one
    nobody did, which is how this defect existed in the first place.
    """
    from dcode_agent import groundedness
    from dcode_api.routes import internal

    assert groundedness.select_symbol_matches is select_symbol_matches
    assert internal.select_symbol_matches is select_symbol_matches


def test_the_evidence_block_offers_ids_instead_of_overloading_inline_code() -> None:
    state = _state_with_definition_locations()
    catalog = graph._build_evidence_catalog(state)
    context = graph._build_llm_context(state, evidence_catalog=catalog)

    symbol_id = next(evidence_id for evidence_id, token in catalog.items() if token == INDEXED)
    location_id = next(
        evidence_id for evidence_id, token in catalog.items() if token == "src/requests/api.py:62"
    )

    assert f"[{symbol_id}] -> `{INDEXED}`" in context
    assert f"[{location_id}] -> `src/requests/api.py:62`" in context
    assert "Evidence catalog (cite ONLY the [C#] IDs" in context
