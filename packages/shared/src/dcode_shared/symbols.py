"""What it means for a name to refer to an indexed symbol. One definition.

`symbols.qualified_name` is built from the repository's directory layout, so the
indexed name for `requests`' module-level helper is `src.requests.api.get` — the
`src.` is a packaging convention of that repository, not part of any import path
anyone writes. A model, or a person, refers to it as `requests.api.get` or
`api.get`.

Two places had to decide whether such a name refers to something real, and they
decided differently:

- `dcode_api.routes.internal` resolved a symbol by **exact match, then dotted
  suffix**, so `api.get` found the row.
- `dcode_agent.groundedness._verify_symbol` used **exact match only**, so the same
  string verified against nothing.

Inside one request the tool therefore answered "yes, here it is" and the guardrail
answered "that does not exist, strip it" — about the same string, over the same
table. Whatever the right rule is, it cannot be two rules, and the guardrail's copy
was the one deciding what a user sees.

**The Python predicate is the authority; SQL only narrows.** `candidate_filter`
returns a superset — every row that could match under either arm — and
`select_symbol_matches` decides which of them do. Expressing the preference twice,
once in SQL and once in Python, would be the same defect one layer down.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement


def select_symbol_matches(rows: Sequence[Any], symbol: str) -> list[Any]:
    """Rows `symbol` refers to: exact matches if any exist, else dotted suffixes.

    Exact wins outright rather than being merged with the suffix matches. A name
    that fully identifies a row is unambiguous, and letting suffixes in beside it
    would make `api.get` drag in every `*.api.get` in the corpus whenever an exact
    row also existed.

    The leading dot in the suffix is load-bearing: without it `get` would match
    `widget`, and `api.get` would match `legacy_api.get`. Matching has to fall on a
    component boundary.
    """
    exact = [row for row in rows if row.qualified_name == symbol]
    if exact:
        return exact
    return [row for row in rows if row.qualified_name.endswith(f".{symbol}")]


def candidate_filter(column: InstrumentedAttribute[str], symbol: str) -> ColumnElement[bool]:
    """SQL narrowing for the rule above — a superset, never the decision.

    `autoescape=True` is not optional. Python identifiers are full of `_`, which is
    a single-character wildcard in `LIKE`: unescaped, `api._get` would also match
    `api.aget`, `api.bget`, and so on. That is a silent false positive in a
    guardrail, which is the one place this project cannot afford one.
    """
    return or_(column == symbol, column.endswith(f".{symbol}", autoescape=True))
