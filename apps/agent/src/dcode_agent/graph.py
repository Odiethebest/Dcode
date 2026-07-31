"""LangGraph state machine — implements DESIGN.md §2.3.3."""

import inspect
import json
import logging
import re
from typing import Any, cast

from dcode_shared.observability import log_event
from dcode_shared.schemas import CallDirection
from dcode_shared.settings import shared_settings
from langgraph.graph import END, START, StateGraph

from dcode_agent import groundedness
from dcode_agent.llm import LLMClient, response_language_for
from dcode_agent.settings import agent_settings
from dcode_agent.state import AgentState

logger = logging.getLogger("dcode.agent.graph")

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def contextualize_node(state: AgentState) -> AgentState:
    """Rewrite a follow-up into a standalone query using prior turns.

    Runs only for multi-turn requests when an LLM is available; otherwise a
    no-op (the raw query flows through unchanged, preserving single-turn
    behavior). The rewrite feeds retrieval + planning only — the groundedness
    guardrail is untouched, so history can never introduce an unverifiable
    citation.
    """
    if not state.history:
        return state
    llm = state.runtime.get("llm")
    contextualize = getattr(llm, "contextualize", None)
    if contextualize is None:
        return state
    try:
        rewritten = await contextualize(question=state.query, history=state.history)
    except Exception as exc:  # noqa: BLE001 — a rewrite failure degrades to the raw query
        log_event(
            logger,
            "contextualize_error",
            repo_id=state.repo_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        return state
    resolved = (rewritten or "").strip()
    if not resolved or resolved == state.query:
        return state
    state.raw_query = state.query
    state.query = resolved
    await _emit_thought(state, f"Resolved the follow-up into a standalone question: {resolved}")
    return state


async def plan_node(state: AgentState) -> AgentState:
    """Rule-based planner for the next ReAct tool step."""
    if state.step_count >= agent_settings.max_steps:
        state.pending_tool_name = None
        state.pending_tool_args = {}
        return state

    next_step = _select_next_tool(state)
    if next_step is None:
        state.pending_tool_name = None
        state.pending_tool_args = {}
        return state

    tool_name, tool_args, thought = next_step
    state.pending_tool_name = tool_name
    state.pending_tool_args = tool_args
    state.thoughts.append(thought)
    await _emit_thought(state, thought)
    return state


async def tool_call_node(state: AgentState) -> AgentState:
    """Execute the chosen tool via the registry with a cache lookup.

    A tool failure (invalid planner args, retrieval/graph API error, filesystem
    error) is recorded on ``state.error`` and degrades to synthesis of the
    evidence gathered so far, rather than aborting the whole query.
    """
    if state.pending_tool_name is None:
        return state

    registry = state.runtime.get("tool_registry")
    if registry is None:
        raise RuntimeError("tool registry is missing from state.runtime")

    tool_name = state.pending_tool_name
    tool = registry.get(tool_name)
    if tool is None:
        raise RuntimeError(f"unknown tool: {tool_name}")

    try:
        args_model = tool.ArgsSchema(**state.pending_tool_args)
    except Exception as exc:  # noqa: BLE001 — invalid planner args degrade, not abort
        return await _record_tool_failure(
            state, tool_name, _jsonable_args(state.pending_tool_args), exc
        )

    cache_key = tool.cache_key(state.repo_id, args_model)
    args_payload = args_model.model_dump(mode="json")

    await _emit_tool_call(state, tool_name, args_payload)
    log_event(
        logger,
        "tool_call",
        repo_id=state.repo_id,
        step=state.step_count + 1,
        tool=tool_name,
    )
    cached_payload = await _cache_get(state.runtime.get("tool_cache"), cache_key)
    cached = cached_payload is not None
    try:
        if cached:
            result_payload = json.loads(cast(str, cached_payload))
        else:
            result = await tool.execute(state.repo_id, args_model)
            result_payload = result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 — tool execution failed; degrade, not abort
        return await _record_tool_failure(state, tool_name, args_payload, exc)

    if not cached:
        await _cache_set(state.runtime.get("tool_cache"), cache_key, json.dumps(result_payload))
    log_event(
        logger,
        "tool_result",
        repo_id=state.repo_id,
        step=state.step_count + 1,
        tool=tool_name,
        cached=cached,
    )

    observation = {
        "tool": tool_name,
        "args": args_payload,
        "result": result_payload,
        "cached": cached,
    }
    state.tool_calls.append(
        {
            "step": state.step_count + 1,
            "tool": tool_name,
            "args": args_payload,
            "cache_key": cache_key,
            "cached": cached,
        }
    )
    state.observations.append(observation)
    state.step_count += 1
    await _emit_tool_result(state, tool_name, _summarize_observation(observation))
    state.pending_tool_name = None
    state.pending_tool_args = {}
    return state


async def _record_tool_failure(
    state: AgentState,
    tool_name: str,
    args: dict[str, Any],
    exc: Exception,
) -> AgentState:
    """Record a tool failure on the state and degrade to synthesis.

    Instead of raising (which aborts the whole query in the API layer), store
    the error so the edges route to synthesis and the user still gets an answer
    built from whatever evidence was gathered before the failure.
    """
    message = f"{type(exc).__name__}: {exc}".strip()
    state.error = f"tool '{tool_name}' failed: {message}"
    state.step_count += 1
    state.tool_calls.append(
        {
            "step": state.step_count,
            "tool": tool_name,
            "args": args,
            "error": message,
        }
    )
    log_event(
        logger,
        "tool_error",
        repo_id=state.repo_id,
        step=state.step_count,
        tool=tool_name,
        error=message,
    )
    await _emit_tool_result(state, tool_name, f"error: {message}")
    state.pending_tool_name = None
    state.pending_tool_args = {}
    return state


async def synthesize_node(state: AgentState) -> AgentState:
    """Compose a first-pass answer from the accumulated observations.

    When an LLM synthesis client is configured (``state.runtime['llm']``), it
    streams a grounded, citation-formatted answer from the retrieved evidence
    (each token delta is emitted as a ``partial_answer`` event); otherwise the
    rule-based template is used. Either way the groundedness node then verifies
    and redacts citations, so the LLM cannot introduce unverified references.
    """
    answer, citations = _synthesize_from_observations(state)

    streamed = False
    llm = state.runtime.get("llm")
    if llm is not None and state.observations:
        llm_answer = await _llm_stream(state, llm)
        if llm_answer is not None:
            # The groundedness node re-extracts citations from the answer text,
            # so the template citations are dropped in favour of the LLM prose.
            answer, citations = llm_answer, []
            streamed = True

    if state.error is not None:
        answer = _prepend_tool_failure_notice(
            answer,
            state.error,
            chinese=_answer_in_chinese(state),
        )
    state.draft_answer = answer
    state.citations = citations
    if not streamed:
        # Non-streaming (template) path: emit the whole draft as one delta so the
        # client sees a pre-final answer via the same partial_answer channel.
        await _emit_partial_answer(state, answer)
    return state


async def _llm_stream(state: AgentState, llm: LLMClient) -> str | None:
    """Stream the LLM answer, emitting each delta live; return the full text.

    Returns ``None`` on empty context or any failure so synthesis degrades to
    the rule-based template.
    """
    evidence_catalog = _build_evidence_catalog(state)
    context = _build_llm_context(state, evidence_catalog=evidence_catalog)
    if not context.strip():
        return None
    await _emit_thought(state, "Synthesize a grounded answer from the retrieved evidence.")
    parts: list[str] = []
    try:
        async for delta in llm.stream(
            question=state.query,
            context=context,
            response_language=response_language_for(state.raw_query or state.query),
        ):
            if not delta:
                continue
            parts.append(delta)
            await _emit_partial_answer(state, delta)
    except Exception as exc:  # noqa: BLE001 — LLM failure degrades to template synthesis
        log_event(
            logger,
            "synthesis_error",
            repo_id=state.repo_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        return None
    text = "".join(parts).strip()
    if not text:
        return None
    # Set this only after successful LLM synthesis. If streaming fails and the
    # template fallback runs, groundedness must retain the legacy parser.
    state.evidence_catalog = evidence_catalog
    return text


_LLM_CONTENT_CHARS = 1200  # cap per-chunk content included in the LLM context


def _build_llm_context(
    state: AgentState,
    *,
    evidence_catalog: dict[str, str] | None = None,
) -> str:
    """Render the retrieved evidence (code + graph locations) for the LLM."""
    catalog = evidence_catalog if evidence_catalog is not None else _build_evidence_catalog(state)
    evidence_id_for = {token: f"[{evidence_id}]" for evidence_id, token in catalog.items()}
    blocks: list[str] = []
    for observation in state.observations:
        tool_name = observation["tool"]
        result = observation["result"]
        if tool_name == "search_code":
            for chunk in result.get("chunks", [])[:5]:
                token = f"{chunk['file_path']}:{chunk['start_line']}"
                blocks.append(
                    f"[Evidence {evidence_id_for[token]}] {token} "
                    f"symbol `{chunk['symbol_name']}`\n{_clip(chunk.get('content', ''))}"
                )
        elif tool_name == "read_file":
            start_line, end_line = result["line_range"]
            token = f"{result['path']}:{start_line}"
            blocks.append(
                f"[Evidence {evidence_id_for[token]}] {result['path']}:{start_line}-{end_line} "
                "(file excerpt)\n"
                f"{_clip(result.get('content', ''))}"
            )
        elif tool_name == "get_call_neighbors":
            call_lines = [
                f"Requested symbol `{result['symbol']}`; direction `{result['direction']}`.",
                "Only entries below are resolved static call edges.",
            ]
            for heading, key in (
                ("matched definitions", "matches"),
                ("callers (incoming calls)", "callers"),
                ("callees (outgoing calls)", "callees"),
            ):
                call_lines.append(f"{heading}:")
                locations = result.get(key, [])
                if not locations:
                    call_lines.append("- none resolved")
                    continue
                for loc in locations[:10]:
                    location_token = f"{loc['file_path']}:{loc['line']}"
                    call_lines.append(
                        f"- {evidence_id_for[location_token]} `{loc['symbol']}` at {location_token}"
                    )
            call_lines.append(
                "A call expression visible only in a file excerpt is source-level "
                "evidence, not a resolved target; describe that limitation explicitly."
            )
            blocks.append("[get_call_neighbors results]\n" + "\n".join(call_lines))
        elif "locations" in result:
            loc_lines = []
            for loc in result["locations"][:10]:
                location_token = f"{loc['file_path']}:{loc['line']}"
                symbol_token = str(loc["symbol"])
                symbol_evidence = evidence_id_for.get(symbol_token)
                suffix = f"; symbol evidence {symbol_evidence}" if symbol_evidence else ""
                loc_lines.append(
                    f"- {evidence_id_for[location_token]} `{symbol_token}` at "
                    f"{location_token}{suffix}"
                )
            if loc_lines:
                blocks.append(f"[{tool_name} results]\n" + "\n".join(loc_lines))
        elif "entries" in result:
            names = ", ".join(str(entry["name"]) for entry in result["entries"][:20])
            blocks.append(f"[directory listing]\n{names}")

    if catalog:
        blocks.append(
            "Evidence catalog (cite ONLY the [C#] IDs; never copy the target as a citation):\n"
            + "\n".join(f"- [{evidence_id}] -> `{token}`" for evidence_id, token in catalog.items())
        )
    return "\n\n".join(blocks)


def _build_evidence_catalog(state: AgentState) -> dict[str, str]:
    """Assign stable request-local IDs to server-owned evidence tokens."""
    return {f"C{index}": token for index, token in enumerate(_allowed_citations(state), start=1)}


def _allowed_citations(state: AgentState) -> list[str]:
    """Canonical evidence targets supported by observations.

    The LLM never cites these strings directly. ``_build_evidence_catalog`` gives
    each one a request-local ``[C#]`` ID, and groundedness resolves the ID back to
    this server-owned target before applying the existing DB verification rules.
    Keeping qualified names here preserves the shared symbol-resolution invariant
    without overloading every dotted inline-code token as a citation.
    """
    allowed: list[str] = []
    seen: set[str] = set()

    def add(token: str) -> None:
        if token and token not in seen:
            seen.add(token)
            allowed.append(token)

    for observation in state.observations:
        tool_name = observation["tool"]
        result = observation["result"]
        if tool_name == "search_code":
            for chunk in result.get("chunks", []):
                add(f"{chunk['file_path']}:{chunk['start_line']}")
        elif tool_name == "read_file":
            add(f"{result['path']}:{result['line_range'][0]}")
        elif tool_name == "get_call_neighbors":
            for key in ("matches", "callers", "callees"):
                for location in result.get(key, []):
                    add(f"{location['file_path']}:{location['line']}")
                    symbol = str(location["symbol"])
                    if "." in symbol:
                        add(symbol)
        elif "locations" in result:
            for location in result["locations"]:
                add(f"{location['file_path']}:{location['line']}")
                symbol = str(location["symbol"])
                if "." in symbol:
                    add(symbol)
    return allowed


def _clip(text: object) -> str:
    rendered = str(text)
    if len(rendered) <= _LLM_CONTENT_CHARS:
        return rendered
    return rendered[:_LLM_CONTENT_CHARS] + "\n... [truncated]"


def _answer_in_chinese(state: AgentState) -> bool:
    return response_language_for(state.raw_query or state.query) == "Chinese"


def _prepend_tool_failure_notice(answer: str, error: str, *, chinese: bool) -> str:
    notice = (
        f"⚠️ {error}。以下回答仅基于故障发生前收集到的证据。"
        if chinese
        else f"⚠️ {error}. The answer below is based on the evidence gathered before the failure."
    )
    return f"{notice}\n\n{answer}" if answer else notice


async def groundedness_node(state: AgentState) -> AgentState:
    """Verify citations and enforce the D-2.3.1 groundedness guardrail.

    Unverified references are redacted from the answer and only verified
    citations are surfaced; the recorded score reflects the pre-redaction draft.
    """
    answer = state.draft_answer or ""
    result = await groundedness.verify(
        answer,
        state.repo_id,
        state.runtime.get("db"),
        evidence_catalog=state.evidence_catalog,
    )
    enforced = groundedness.enforce_groundedness(
        answer,
        result,
        threshold=shared_settings.groundedness_threshold,
        chinese=_answer_in_chinese(state),
    )
    state.citations = [
        {
            "symbol": item.symbol,
            "file_path": item.file_path,
            "line": item.line,
            "verified": item.verified,
        }
        for item in enforced.citations
    ]
    state.groundedness_score = enforced.score
    state.final_answer = enforced.answer
    return state


# ---------------------------------------------------------------------------
# Edge logic
# ---------------------------------------------------------------------------


def decide_after_plan(state: AgentState) -> str:
    """Run the planned tool, or stop and synthesize."""
    if state.error is not None:
        return "synthesize"
    if state.step_count >= agent_settings.max_steps:
        return "synthesize"  # forced synthesis at the §2.3.1 cap
    if state.draft_answer is not None:
        return "synthesize"
    if state.pending_tool_name is None:
        return "synthesize"
    return "tool_call"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph() -> Any:
    """Compile the LangGraph state machine for an agent invocation.

    TODO(M2): wire checkpointer + observability hooks per DESIGN.md NFR-5.
    """
    g = StateGraph(AgentState)
    g.add_node("contextualize", contextualize_node)
    g.add_node("plan", plan_node)
    g.add_node("tool_call", tool_call_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("groundedness_check", groundedness_node)

    g.add_edge(START, "contextualize")
    g.add_edge("contextualize", "plan")
    g.add_conditional_edges(
        "plan",
        decide_after_plan,
        {"tool_call": "tool_call", "synthesize": "synthesize"},
    )
    g.add_conditional_edges(
        "tool_call",
        lambda state: "synthesize" if state.error is not None else "plan",
        {"plan": "plan", "synthesize": "synthesize"},
    )
    g.add_edge("synthesize", "groundedness_check")
    g.add_edge("groundedness_check", END)

    return g.compile()


def _select_next_tool(state: AgentState) -> tuple[str, dict[str, Any], str] | None:
    if not state.observations:
        return _select_initial_tool(state.query)
    return _select_followup_tool(state)


def _select_initial_tool(query: str) -> tuple[str, dict[str, Any], str]:
    normalized = query.lower()
    subject = _extract_subject(query)
    path = _extract_path(query)
    call_direction = _call_query_direction(normalized)
    if (
        "outline" in normalized
        or "symbols in" in normalized
        or "functions in" in normalized
        or "classes in" in normalized
    ) and path is not None:
        return (
            "get_file_outline",
            {"path": path},
            f"Route query to get_file_outline for `{path}`.",
        )
    if _is_dependents_query(normalized):
        module = subject or query.strip()
        return (
            "get_dependents",
            {"module": module},
            f"Route query to get_dependents for `{module}`.",
        )
    if "dependency" in normalized or "dependencies" in normalized or "imports" in normalized:
        module = subject or query.strip()
        return (
            "get_dependencies",
            {"module": module},
            f"Route query to get_dependencies for `{module}`.",
        )
    if call_direction is not None:
        call_subject = subject or _extract_call_subject(query)
        if call_subject is not None:
            return (
                "get_call_neighbors",
                {"symbol": call_subject, "direction": call_direction},
                f"Route call-graph query to get_call_neighbors for `{call_subject}` "
                f"({call_direction}).",
            )
        # Pronouns and natural-language descriptions need retrieval to identify
        # the target symbol before the graph can be walked.
        return (
            "search_code",
            {"query": query.strip(), "k": 5},
            "Search for the call-query subject before walking call-graph edges.",
        )
    if _is_reference_query(normalized):
        symbol = subject or _extract_reference_subject(query) or query.strip()
        return (
            "find_references",
            {"symbol": symbol},
            f"Route query to find_references for `{symbol}`.",
        )
    if "definition" in normalized or "where defined" in normalized or " defined" in normalized:
        symbol = subject or query.strip()
        return (
            "find_definition",
            {"symbol": symbol},
            f"Route query to find_definition for `{symbol}`.",
        )
    return (
        "search_code",
        {"query": query.strip(), "k": 5},
        "Route query to search_code for lexical and semantic lookup.",
    )


def _select_followup_tool(state: AgentState) -> tuple[str, dict[str, Any], str] | None:
    call_direction = _call_query_direction(state.query.lower())
    if call_direction is not None:
        return _select_call_followup_tool(state, call_direction)

    if not _needs_multihop(state.query):
        return None

    search = _first_observation(state, "search_code")
    top_chunk = _top_search_chunk(search)
    if top_chunk is None:
        return None

    path = str(top_chunk["file_path"])
    symbol = str(top_chunk["symbol_name"])
    line_range = _chunk_line_range(top_chunk)

    if not _has_tool_call(state, "read_file", {"path": path, "line_range": list(line_range)}):
        return (
            "read_file",
            {"path": path, "line_range": line_range},
            f"Read the top retrieved chunk `{path}:{line_range[0]}` for local context.",
        )

    if symbol != "__module_doc__" and not _has_tool_call(
        state, "find_references", {"symbol": symbol}
    ):
        return (
            "find_references",
            {"symbol": symbol},
            f"Follow graph references for `{symbol}` to expand cross-file context.",
        )

    if not _has_tool_call(state, "get_file_outline", {"path": path}):
        return (
            "get_file_outline",
            {"path": path},
            f"Inspect file outline for `{path}` to summarize nearby structure.",
        )

    return None


def _select_call_followup_tool(
    state: AgentState,
    direction: CallDirection,
) -> tuple[str, dict[str, Any], str] | None:
    neighbors = _last_observation(state, "get_call_neighbors")
    if neighbors is not None:
        matches = neighbors["result"].get("matches", [])
        if matches:
            target = matches[0]
            path = str(target["file_path"])
            start_line = int(target["line"])
            line_range = (start_line, start_line + 80)
            if not _has_read_covering(state, path, start_line):
                return (
                    "read_file",
                    {"path": path, "line_range": line_range},
                    f"Read `{path}:{start_line}` to capture unresolved source-level calls.",
                )
            return None

    search = _first_observation(state, "search_code")
    if search is None:
        return (
            "search_code",
            {"query": state.query.strip(), "k": 5},
            "Search for the unresolved call-query subject.",
        )

    top_chunk = _top_search_chunk(search)
    if top_chunk is None:
        return None

    path = str(top_chunk["file_path"])
    symbol = str(top_chunk["symbol_name"])
    line_range = _chunk_line_range(top_chunk)
    if not _has_tool_call(state, "read_file", {"path": path, "line_range": list(line_range)}):
        return (
            "read_file",
            {"path": path, "line_range": line_range},
            f"Read the candidate `{path}:{line_range[0]}` before walking its call edges.",
        )

    args = {"symbol": symbol, "direction": direction}
    if not _has_tool_call(state, "get_call_neighbors", args):
        return (
            "get_call_neighbors",
            args,
            f"Walk resolved {direction} call edges for `{symbol}`.",
        )
    return None


def _needs_multihop(query: str) -> bool:
    normalized = query.lower()
    return any(
        marker in normalized
        for marker in (
            "how",
            "flow",
            "end-to-end",
            "end to end",
            "architecture",
            "wired",
            "implemented",
            "attach",
            "auth",
            "authentication",
            "call",
            "use",
            "uses",
            "如何",
            "流程",
            "架构",
            "实现",
            "调用",
            "使用",
        )
    )


def _first_observation(state: AgentState, tool_name: str) -> dict[str, Any] | None:
    for observation in state.observations:
        if observation["tool"] == tool_name:
            return observation
    return None


def _last_observation(state: AgentState, tool_name: str) -> dict[str, Any] | None:
    for observation in reversed(state.observations):
        if observation["tool"] == tool_name:
            return observation
    return None


def _top_search_chunk(observation: dict[str, Any] | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    chunks = observation["result"].get("chunks", [])
    if not chunks:
        return None
    return cast(dict[str, Any], chunks[0])


def _chunk_line_range(chunk: dict[str, Any]) -> tuple[int, int]:
    start_line = int(chunk["start_line"])
    end_line = int(chunk["end_line"])
    return (start_line, min(end_line, start_line + 80))


def _has_tool_call(state: AgentState, tool_name: str, args: dict[str, Any]) -> bool:
    normalized_args = _jsonable_args(args)
    return any(
        call["tool"] == tool_name and call["args"] == normalized_args for call in state.tool_calls
    )


def _has_read_covering(state: AgentState, path: str, line: int) -> bool:
    for call in state.tool_calls:
        if call["tool"] != "read_file":
            continue
        args = call["args"]
        if args.get("path") != path:
            continue
        line_range = args.get("line_range")
        if (
            isinstance(line_range, list)
            and len(line_range) == 2
            and int(line_range[0]) <= line <= int(line_range[1])
        ):
            return True
    return False


def _jsonable_args(args: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(args)))


def _extract_subject(query: str) -> str | None:
    backticked = cast(list[str], re.findall(r"`([^`]+)`", query))
    if backticked:
        return backticked[0]

    symbol_match = re.search(r"([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)", query)
    if symbol_match:
        return symbol_match.group(1)

    quoted = cast(list[str], re.findall(r'"([^"]+)"', query))
    if quoted:
        return quoted[0]
    return None


def _is_reference_query(normalized_query: str) -> bool:
    return any(
        marker in normalized_query
        for marker in (
            "who references",
            "references",
            "谁引用",
            "引用了",
        )
    )


def _is_dependents_query(normalized_query: str) -> bool:
    """Incoming-dependency phrasings ("what imports X" / reverse dependencies).

    Checked before the outgoing-`get_dependencies` route so incoming phrasing
    wins. Deliberately avoids the ambiguous bare "imports" / "depends on".
    """
    return any(
        marker in normalized_query
        for marker in (
            "dependent",
            "imported by",
            "importers",
            "who imports",
            "used by",
            "reverse dependenc",
        )
    )


def _extract_reference_subject(query: str) -> str | None:
    patterns = (
        r"\bwho\s+references\s+([A-Za-z_][\w.]*)\b",
        r"\breferences\s+(?:to\s+|of\s+)?([A-Za-z_][\w.]*)\b",
        r"(?:谁引用|引用了)\s*([A-Za-z_][\w.]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _call_query_direction(normalized_query: str) -> CallDirection | None:
    """Classify explicit caller/callee intent in English or Chinese."""
    caller_markers = (
        "who calls",
        "called by",
        "caller",
        "被哪些函数调用",
        "被哪些方法调用",
        "被哪个函数调用",
        "被哪个方法调用",
        "被调用",
        "谁调用",
        "谁在调用",
        "哪些函数调用",
        "哪些方法调用",
    )
    callee_markers = (
        "callee",
        "calls what",
        "calls which",
        "调用哪些",
        "调用哪个",
        "调用了哪些",
        "调用了谁",
        "调用谁",
        "调用什么",
        "调用了什么",
    )
    asks_callers = any(marker in normalized_query for marker in caller_markers)
    asks_callers = asks_callers or bool(
        re.search(
            r"\b(?:what|which\s+(?:functions?|methods?))\s+calls?\b",
            normalized_query,
        )
    )
    asks_callees = any(marker in normalized_query for marker in callee_markers)
    asks_callees = asks_callees or bool(
        re.search(r"\b(?:what|which)\b.*\b(?:does|do)\b.*\bcall\b", normalized_query)
    )

    if "调用关系" in normalized_query or (asks_callers and asks_callees):
        return "both"
    if asks_callers:
        return "callers"
    if asks_callees:
        return "callees"
    return None


def _extract_call_subject(query: str) -> str | None:
    identifier = r"([A-Za-z_][\w.]*)"
    patterns = (
        rf"\bwho\s+calls\s+{identifier}\b",
        rf"\bfind\s+callers?\s+(?:of\s+)?{identifier}\b",
        rf"\bcallers?\s+(?:of\s+)?{identifier}\b",
        rf"\b(?:what|which\s+(?:functions?|methods?))\s+calls?\s+{identifier}\b",
        rf"\b(?:what|which)\b.*\b(?:does|do)\s+{identifier}\s+call\b",
        rf"\bcallees?\s+(?:of\s+)?{identifier}\b",
        rf"(?:谁|哪些函数|哪些方法)(?:在)?调用\s*{identifier}",
        rf"{identifier}\s*被(?:哪些函数|哪些方法|哪个函数|哪个方法)?调用",
        rf"{identifier}\s*调用(?:了)?(?:哪些|哪个|谁|什么)",
    )
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_path(query: str) -> str | None:
    matches = cast(list[str], re.findall(r"[\w./\\-]+\.py", query))
    return matches[0] if matches else None


async def _emit_thought(state: AgentState, thought: str) -> None:
    emitter = state.runtime.get("emitter")
    if emitter is None:
        return
    await emitter.emit_thought(step=state.step_count + 1, content=thought)


async def _emit_tool_call(state: AgentState, tool_name: str, args: dict[str, Any]) -> None:
    emitter = state.runtime.get("emitter")
    if emitter is None:
        return
    await emitter.emit_tool_call(step=state.step_count + 1, tool=tool_name, args=args)


async def _emit_tool_result(state: AgentState, tool_name: str, summary: str) -> None:
    emitter = state.runtime.get("emitter")
    if emitter is None:
        return
    await emitter.emit_tool_result(step=state.step_count, tool=tool_name, result_summary=summary)


async def _emit_partial_answer(state: AgentState, delta: str) -> None:
    emitter = state.runtime.get("emitter")
    if emitter is None:
        return
    await emitter.emit_partial_answer(delta)


async def _cache_get(cache: Any, key: str) -> str | None:
    if cache is None:
        return None
    if isinstance(cache, dict):
        value = cache.get(key)
    else:
        value = cache.get(key)
        if inspect.isawaitable(value):
            value = await value
    return cast(str | None, value)


async def _cache_set(cache: Any, key: str, value: str) -> None:
    if cache is None:
        return
    if isinstance(cache, dict):
        cache[key] = value
        return
    result = cache.set(key, value, ex=shared_settings.tool_cache_ttl_seconds)
    if inspect.isawaitable(result):
        await result


def _summarize_observation(observation: dict[str, Any]) -> str:
    tool_name = observation["tool"]
    result = observation["result"]
    cached_prefix = "cache hit; " if observation.get("cached") else ""
    if tool_name == "search_code":
        chunks = result.get("chunks", [])
        if not chunks:
            return cached_prefix + "0 chunk results"
        top = chunks[0]
        return cached_prefix + f"{len(chunks)} chunks; top {top['file_path']}:{top['start_line']}"
    if tool_name == "get_call_neighbors":
        matches = result.get("matches", [])
        callers = result.get("callers", [])
        callees = result.get("callees", [])
        return (
            cached_prefix
            + f"{len(matches)} matches; {len(callers)} callers; {len(callees)} callees"
        )
    if "locations" in result:
        locations = result["locations"]
        if not locations:
            return cached_prefix + "0 locations"
        top = locations[0]
        return cached_prefix + f"{len(locations)} locations; top {top['file_path']}:{top['line']}"
    if "content" in result:
        return (
            cached_prefix
            + f"read {result['path']} lines {result['line_range'][0]}-{result['line_range'][1]}"
        )
    if "entries" in result:
        return cached_prefix + f"{len(result['entries'])} directory entries"
    return cached_prefix + "tool completed"


def _synthesize_from_observations(state: AgentState) -> tuple[str, list[dict[str, Any]]]:
    chinese = _answer_in_chinese(state)
    if not state.observations:
        message = (
            "此查询未产生可用的检索结果。"
            if chinese
            else "No observations were produced for this query."
        )
        return (message, [])

    if len(state.observations) > 1:
        return _synthesize_multihop(state)

    observation = state.observations[-1]
    tool_name = observation["tool"]
    result = observation["result"]

    if tool_name == "search_code":
        chunks = result["chunks"]
        if not chunks:
            message = (
                f"没有找到与 `{state.query}` 匹配的已索引代码片段。"
                if chinese
                else f"No indexed chunks matched `{state.query}`."
            )
            return (message, [])
        lines = [
            (
                f"与 `{state.query}` 最相关的代码结果："
                if chinese
                else f"Top code hits for `{state.query}`:"
            )
        ]
        citations: list[dict[str, Any]] = []
        for chunk in chunks[:3]:
            citation = {
                "symbol": chunk["symbol_name"],
                "file_path": chunk["file_path"],
                "line": chunk["start_line"],
            }
            citations.append(citation)
            lines.append(
                f"- `{chunk['symbol_name']}`，位于 `{chunk['file_path']}:{chunk['start_line']}`"
                if chinese
                else f"- `{chunk['symbol_name']}` in `{chunk['file_path']}:{chunk['start_line']}`"
            )
        return ("\n".join(lines), citations)

    if tool_name == "get_call_neighbors":
        if not result["found"]:
            message = (
                f"没有找到与 `{result['symbol']}` 匹配的已索引符号。"
                if chinese
                else f"No indexed symbol matched `{result['symbol']}`."
            )
            return (message, [])

        lines = [
            (
                f"`{result['symbol']}` 的静态调用关系："
                if chinese
                else f"Resolved static call relationships for `{result['symbol']}`:"
            )
        ]
        citations = []
        for heading, key in (
            ("匹配定义" if chinese else "Matched definitions", "matches"),
            ("调用它的函数" if chinese else "Callers", "callers"),
            ("它调用的函数" if chinese else "Callees", "callees"),
        ):
            lines.append(f"- {heading}:")
            locations = result[key]
            if not locations:
                lines.append("  - 未解析到结果。" if chinese else "  - None resolved.")
                continue
            for location in locations[:5]:
                citation = _citation_from_location(location)
                _append_unique_citation(citations, citation)
                lines.append(
                    f"  - `{location['symbol']}`，位于 `{location['file_path']}:{location['line']}`"
                    if chinese
                    else f"  - `{location['symbol']}` at "
                    f"`{location['file_path']}:{location['line']}`"
                )
        return ("\n".join(lines), citations)

    if tool_name in {
        "find_definition",
        "find_references",
        "get_dependencies",
        "get_dependents",
        "get_file_outline",
        "grep",
    }:
        locations = result["locations"]
        if not locations:
            message = (
                f"没有找到与 `{state.query}` 相关的结果。"
                if chinese
                else f"No results found for `{state.query}`."
            )
            return (message, [])
        heading = (
            {
                "find_definition": "定义匹配：",
                "find_references": "引用匹配：",
                "get_dependencies": "依赖项匹配：",
                "get_dependents": "被依赖项匹配：",
                "get_file_outline": "文件结构：",
                "grep": "精确匹配：",
            }
            if chinese
            else {
                "find_definition": "Definition matches:",
                "find_references": "Reference matches:",
                "get_dependencies": "Dependency matches:",
                "get_dependents": "Dependent matches:",
                "get_file_outline": "File outline:",
                "grep": "Exact matches:",
            }
        )[tool_name]
        lines = [heading]
        citations = []
        for location in locations[:5]:
            citations.append(
                {
                    "symbol": location["symbol"],
                    "file_path": location["file_path"],
                    "line": location["line"],
                }
            )
            lines.append(
                f"- `{location['symbol']}`，位于 `{location['file_path']}:{location['line']}`"
                if chinese
                else f"- `{location['symbol']}` at `{location['file_path']}:{location['line']}`"
            )
        return ("\n".join(lines), citations)

    if tool_name == "read_file":
        start_line, end_line = result["line_range"]
        citation = {
            "symbol": result["path"],
            "file_path": result["path"],
            "line": start_line,
        }
        answer = (
            f"摘自 `{result['path']}:{start_line}`-`{end_line}`：\n"
            if chinese
            else f"Excerpt from `{result['path']}:{start_line}`-`{end_line}`:\n"
        ) + f"```python\n{result['content']}\n```"
        return (answer, [citation])

    if tool_name == "list_directory":
        entries = result["entries"]
        lines = ["目录内容：" if chinese else "Directory entries:"]
        for entry in entries[:10]:
            lines.append(
                f"- `{entry['name']}`（{entry['kind']}）"
                if chinese
                else f"- `{entry['name']}` ({entry['kind']})"
            )
        return ("\n".join(lines), [])

    return ("工具执行完成。" if chinese else "Tool execution completed.", [])


def _synthesize_multihop(state: AgentState) -> tuple[str, list[dict[str, Any]]]:
    chinese = _answer_in_chinese(state)
    lines = [
        (
            f"针对 `{state.query}` 的 Agent 检索过程："
            if chinese
            else f"Agent trace for `{state.query}`:"
        )
    ]
    citations: list[dict[str, Any]] = []

    for observation in state.observations:
        tool_name = observation["tool"]
        result = observation["result"]

        if tool_name == "search_code":
            chunks = result["chunks"]
            if not chunks:
                lines.append(
                    "- `search_code` 未找到已索引代码片段。"
                    if chinese
                    else "- `search_code` found no indexed chunks."
                )
                continue
            lines.append(
                "- `search_code` 找到以下可能的入口："
                if chinese
                else "- `search_code` found these likely entry points:"
            )
            for chunk in chunks[:3]:
                citation = _citation_from_chunk(chunk)
                _append_unique_citation(citations, citation)
                lines.append(
                    f"  - `{chunk['symbol_name']}`，位于 "
                    f"`{chunk['file_path']}:{chunk['start_line']}`"
                    if chinese
                    else f"  - `{chunk['symbol_name']}` in "
                    f"`{chunk['file_path']}:{chunk['start_line']}`"
                )
            continue

        if tool_name == "read_file":
            start_line, end_line = result["line_range"]
            citation = {
                "symbol": result["path"],
                "file_path": result["path"],
                "line": start_line,
            }
            _append_unique_citation(citations, citation)
            lines.append(
                f"- `read_file` 检查了 `{result['path']}:{start_line}`-"
                f"`{end_line}`，以了解局部实现。"
                if chinese
                else f"- `read_file` inspected `{result['path']}:{start_line}`-"
                f"`{end_line}` for local implementation context."
            )
            continue

        if tool_name == "get_call_neighbors":
            if not result["found"]:
                lines.append(
                    f"- `get_call_neighbors` 未找到 `{result['symbol']}`。"
                    if chinese
                    else f"- `get_call_neighbors` did not resolve `{result['symbol']}`."
                )
                continue
            lines.append(
                "- `get_call_neighbors` 将静态调用边按方向分组："
                if chinese
                else "- `get_call_neighbors` grouped resolved static call edges by direction:"
            )
            for heading, key in (
                ("匹配定义" if chinese else "matched definitions", "matches"),
                ("调用方" if chinese else "callers", "callers"),
                ("被调用方" if chinese else "callees", "callees"),
            ):
                locations = result[key]
                lines.append(f"  - {heading}:")
                if not locations:
                    lines.append("    - 未解析到结果。" if chinese else "    - none resolved.")
                    continue
                for location in locations[:5]:
                    citation = _citation_from_location(location)
                    _append_unique_citation(citations, citation)
                    lines.append(
                        f"    - `{location['symbol']}`，位于 "
                        f"`{location['file_path']}:{location['line']}`"
                        if chinese
                        else f"    - `{location['symbol']}` at "
                        f"`{location['file_path']}:{location['line']}`"
                    )
            continue

        if tool_name in {
            "find_definition",
            "find_references",
            "get_dependencies",
            "get_dependents",
            "get_file_outline",
            "grep",
        }:
            locations = result["locations"]
            if not locations:
                lines.append(
                    f"- `{tool_name}` 未找到位置。"
                    if chinese
                    else f"- `{tool_name}` found no locations."
                )
                continue
            heading = (
                {
                    "find_definition": "定义位置",
                    "find_references": "跨文件引用",
                    "get_dependencies": "模块依赖",
                    "get_dependents": "反向依赖",
                    "get_file_outline": "附近文件符号",
                    "grep": "精确匹配",
                }
                if chinese
                else {
                    "find_definition": "definition locations",
                    "find_references": "cross-file references",
                    "get_dependencies": "module dependencies",
                    "get_dependents": "reverse dependencies",
                    "get_file_outline": "nearby file symbols",
                    "grep": "exact matches",
                }
            )[tool_name]
            lines.append(
                f"- `{tool_name}` 补充了{heading}："
                if chinese
                else f"- `{tool_name}` added {heading}:"
            )
            for location in locations[:5]:
                citation = _citation_from_location(location)
                _append_unique_citation(citations, citation)
                lines.append(
                    f"  - `{location['symbol']}`，位于 `{location['file_path']}:{location['line']}`"
                    if chinese
                    else f"  - `{location['symbol']}` at "
                    f"`{location['file_path']}:{location['line']}`"
                )
            continue

        if tool_name == "list_directory":
            lines.append(
                f"- `list_directory` 返回了 {len(result['entries'])} 个条目。"
                if chinese
                else f"- `list_directory` returned {len(result['entries'])} entries."
            )

    return ("\n".join(lines), citations)


def _citation_from_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": chunk["symbol_name"],
        "file_path": chunk["file_path"],
        "line": chunk["start_line"],
    }


def _citation_from_location(location: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": location["symbol"],
        "file_path": location["file_path"],
        "line": location["line"],
    }


def _append_unique_citation(citations: list[dict[str, Any]], citation: dict[str, Any]) -> None:
    key = (citation["symbol"], citation["file_path"], citation["line"])
    if any((item["symbol"], item["file_path"], item["line"]) == key for item in citations):
        return
    citations.append(citation)
