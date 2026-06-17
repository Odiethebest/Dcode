# Dcode Final Report

## Summary

Dcode is a structure-aware code understanding stack built around four runtime surfaces:

- async indexing (`POST /api/v1/repos` → worker pipeline)
- internal retrieval / graph APIs
- SSE-based agent answers with grounded citations
- an evaluation harness and comparison UI

As of **2026-06-16**, the repository delivers a complete local vertical slice:

- a real indexing pipeline for Python repositories
- retrieval and graph lookup endpoints
- a working agent loop with 8 tools
- a frontend for indexing, querying, and baseline comparison
- a production-shaped Docker Compose package with static frontend serving

## Implemented System

### Indexing

- `git clone --depth=1`
- Python `ast` parse
- AST-boundary chunking for module docstrings, functions, classes, and methods
- chunk persistence with embedding cache
- graph rebuild with symbol definitions and module-level import edges

### Retrieval and Agent

- `/internal/search`
- `/internal/find_definition`
- `/internal/find_references`
- `/internal/get_dependencies`
- `/internal/get_file_outline`
- agent SSE events: `thought`, `tool_call`, `tool_result`, `citation`, `partial_answer`, `final_answer`, `error`
- groundedness verification against `chunks` and `symbols`

### Frontend and Deployment

- `Index` page for repo submission and stage tracking
- `Query` page for live SSE rendering
- `Compare` page for baseline snapshots
- nginx-hosted static frontend image
- `docker-compose.prod.yml` with frontend-only public exposure and `/api/*` proxying

## Evaluation Snapshot

The recorded suite in `results/eval-suite/` uses 16 manually curated `requests` questions.

Aggregate metrics:

| Baseline | Recall@5 | MRR | nDCG@5 | Groundedness |
|---|---:|---:|---:|---:|
| B2 | 0.1979 | 0.2125 | 0.1917 | 1.00 |
| B3 | 0.1979 | 0.2125 | 0.1917 | 1.00 |
| B4 | 0.1979 | 0.2125 | 0.1917 | 0.95 |

L2/L3 composite margins for B4:

- vs B2 on L2: `-0.0125`
- vs B3 on L2: `-0.0125`
- vs B2 on L3: `-0.0333`
- vs B3 on L3: `-0.0333`

Result: **H1 unsupported**.

## What Worked

- The repo now has a defensible vertical slice rather than disconnected stubs.
- `repo_id` isolation, caches, and internal-route protection are enforced in code and tests.
- The production packaging path is now explicit and locally smoke-tested.
- Groundedness stayed at the threshold floor for B4 (`0.95`), so citation verification is doing useful work.

## What Did Not Land

- real query-side dense retrieval
- real reranker
- richer graph edges (`calls`, broader references, inheritance)
- Judge / pairwise answer scoring
- public DNS / external demo availability

Those missing pieces explain why the current evaluation does not support H1.

## Recommended Next Steps

1. Replace stub embedding with the selected code embedding model.
2. Wire a real reranker.
3. Expand graph coverage beyond module imports.
4. Re-run the suite before touching prompt-level answer generation.
5. Only after retrieval quality moves, finish external DNS and public deployment.
