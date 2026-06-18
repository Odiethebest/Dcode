"""LangGraph state machine — implements DESIGN.md §2.3.3."""

import inspect
import json
import logging
import re
from typing import Any, cast

from dcode_shared.observability import log_event
from dcode_shared.settings import shared_settings
from langgraph.graph import END, START, StateGraph

from dcode_agent import groundedness
from dcode_agent.state import MAX_STEPS, AgentState

logger = logging.getLogger("dcode.agent.graph")

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def plan_node(state: AgentState) -> AgentState:
    """Rule-based planner for the next ReAct tool step."""
    if state.step_count >= MAX_STEPS:
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
    """Execute the chosen tool via the registry with a cache lookup."""
    if state.pending_tool_name is None:
        return state

    registry = state.runtime.get("tool_registry")
    if registry is None:
        raise RuntimeError("tool registry is missing from state.runtime")

    tool = registry.get(state.pending_tool_name)
    if tool is None:
        raise RuntimeError(f"unknown tool: {state.pending_tool_name}")

    args_model = tool.ArgsSchema(**state.pending_tool_args)
    cache_key = tool.cache_key(state.repo_id, args_model)

    await _emit_tool_call(state, state.pending_tool_name, args_model.model_dump(mode="json"))
    log_event(
        logger,
        "tool_call",
        repo_id=state.repo_id,
        step=state.step_count + 1,
        tool=state.pending_tool_name,
    )
    cached_payload = await _cache_get(state.runtime.get("tool_cache"), cache_key)
    cached = cached_payload is not None
    if cached:
        result_payload = json.loads(cast(str, cached_payload))
    else:
        result = await tool.execute(state.repo_id, args_model)
        result_payload = result.model_dump(mode="json")
        await _cache_set(state.runtime.get("tool_cache"), cache_key, json.dumps(result_payload))
    log_event(
        logger,
        "tool_result",
        repo_id=state.repo_id,
        step=state.step_count + 1,
        tool=state.pending_tool_name,
        cached=cached,
    )

    observation = {
        "tool": state.pending_tool_name,
        "args": args_model.model_dump(mode="json"),
        "result": result_payload,
        "cached": cached,
    }
    state.tool_calls.append(
        {
            "step": state.step_count + 1,
            "tool": state.pending_tool_name,
            "args": args_model.model_dump(mode="json"),
            "cache_key": cache_key,
            "cached": cached,
        }
    )
    state.observations.append(observation)
    state.step_count += 1
    await _emit_tool_result(state, state.pending_tool_name, _summarize_observation(observation))
    state.pending_tool_name = None
    state.pending_tool_args = {}
    return state


async def synthesize_node(state: AgentState) -> AgentState:
    """Compose a first-pass answer from the accumulated observations."""
    answer, citations = _synthesize_from_observations(state)
    state.draft_answer = answer
    state.citations = citations
    return state


async def groundedness_node(state: AgentState) -> AgentState:
    """Verify extracted citations and finalize the answer."""
    answer = state.draft_answer or ""
    result = await groundedness.verify(answer, state.repo_id, state.runtime.get("db"))
    state.citations = [
        {
            "symbol": item.symbol,
            "file_path": item.file_path,
            "line": item.line,
            "verified": item.verified,
        }
        for item in result.citations
    ]
    state.groundedness_score = result.score
    state.final_answer = answer
    return state


# ---------------------------------------------------------------------------
# Edge logic
# ---------------------------------------------------------------------------


def decide_after_plan(state: AgentState) -> str:
    """Run the planned tool, or stop and synthesize."""
    if state.error is not None:
        return "synthesize"
    if state.step_count >= MAX_STEPS:
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
    g.add_node("plan", plan_node)
    g.add_node("tool_call", tool_call_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("groundedness_check", groundedness_node)

    g.add_edge(START, "plan")
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
    if "dependency" in normalized or "dependencies" in normalized or "imports" in normalized:
        module = subject or query.strip()
        return (
            "get_dependencies",
            {"module": module},
            f"Route query to get_dependencies for `{module}`.",
        )
    if "who calls" in normalized or "who references" in normalized or "references" in normalized:
        symbol = subject or query.strip()
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
        )
    )


def _first_observation(state: AgentState, tool_name: str) -> dict[str, Any] | None:
    for observation in state.observations:
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
    if "locations" in result:
        locations = result["locations"]
        if not locations:
            return cached_prefix + "0 locations"
        top = locations[0]
        return cached_prefix + f"{len(locations)} locations; top {top['file_path']}:{top['line']}"
    if "content" in result:
        return cached_prefix + f"read {result['path']} lines {result['line_range'][0]}-{result['line_range'][1]}"
    if "entries" in result:
        return cached_prefix + f"{len(result['entries'])} directory entries"
    return cached_prefix + "tool completed"


def _synthesize_from_observations(state: AgentState) -> tuple[str, list[dict[str, Any]]]:
    if not state.observations:
        return ("No observations were produced for this query.", [])

    if len(state.observations) > 1:
        return _synthesize_multihop(state)

    observation = state.observations[-1]
    tool_name = observation["tool"]
    result = observation["result"]

    if tool_name == "search_code":
        chunks = result["chunks"]
        if not chunks:
            return (f"No indexed chunks matched `{state.query}`.", [])
        lines = [f"Top code hits for `{state.query}`:"]
        citations: list[dict[str, Any]] = []
        for chunk in chunks[:3]:
            citation = {
                "symbol": chunk["symbol_name"],
                "file_path": chunk["file_path"],
                "line": chunk["start_line"],
            }
            citations.append(citation)
            lines.append(
                f"- `{chunk['symbol_name']}` in `{chunk['file_path']}:{chunk['start_line']}`"
            )
        return ("\n".join(lines), citations)

    if tool_name in {"find_definition", "find_references", "get_dependencies", "get_file_outline", "grep"}:
        locations = result["locations"]
        if not locations:
            return (f"No results found for `{state.query}`.", [])
        heading = {
            "find_definition": "Definition matches:",
            "find_references": "Reference matches:",
            "get_dependencies": "Dependency matches:",
            "get_file_outline": "File outline:",
            "grep": "Exact matches:",
        }[tool_name]
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
            lines.append(f"- `{location['symbol']}` at `{location['file_path']}:{location['line']}`")
        return ("\n".join(lines), citations)

    if tool_name == "read_file":
        start_line, end_line = result["line_range"]
        citation = {
            "symbol": result["path"],
            "file_path": result["path"],
            "line": start_line,
        }
        answer = (
            f"Excerpt from `{result['path']}:{start_line}`-`{end_line}`:\n"
            f"```python\n{result['content']}\n```"
        )
        return (answer, [citation])

    if tool_name == "list_directory":
        entries = result["entries"]
        lines = ["Directory entries:"]
        for entry in entries[:10]:
            lines.append(f"- `{entry['name']}` ({entry['kind']})")
        return ("\n".join(lines), [])

    return ("Tool execution completed.", [])


def _synthesize_multihop(state: AgentState) -> tuple[str, list[dict[str, Any]]]:
    lines = [f"Agent trace for `{state.query}`:"]
    citations: list[dict[str, Any]] = []

    for observation in state.observations:
        tool_name = observation["tool"]
        result = observation["result"]

        if tool_name == "search_code":
            chunks = result["chunks"]
            if not chunks:
                lines.append("- `search_code` found no indexed chunks.")
                continue
            lines.append("- `search_code` found these likely entry points:")
            for chunk in chunks[:3]:
                citation = _citation_from_chunk(chunk)
                _append_unique_citation(citations, citation)
                lines.append(
                    f"  - `{chunk['symbol_name']}` in `{chunk['file_path']}:{chunk['start_line']}`"
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
                f"- `read_file` inspected `{result['path']}:{start_line}`-`{end_line}` for local implementation context."
            )
            continue

        if tool_name in {"find_definition", "find_references", "get_dependencies", "get_file_outline", "grep"}:
            locations = result["locations"]
            if not locations:
                lines.append(f"- `{tool_name}` found no locations.")
                continue
            heading = {
                "find_definition": "definition locations",
                "find_references": "cross-file references",
                "get_dependencies": "module dependencies",
                "get_file_outline": "nearby file symbols",
                "grep": "exact matches",
            }[tool_name]
            lines.append(f"- `{tool_name}` added {heading}:")
            for location in locations[:5]:
                citation = _citation_from_location(location)
                _append_unique_citation(citations, citation)
                lines.append(
                    f"  - `{location['symbol']}` at `{location['file_path']}:{location['line']}`"
                )
            continue

        if tool_name == "list_directory":
            lines.append(f"- `list_directory` returned {len(result['entries'])} entries.")

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
