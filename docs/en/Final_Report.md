# Dcode Final Report

## Summary

Dcode is a structure-aware code understanding stack built around four runtime surfaces:

- async indexing (`POST /api/v1/repos` → worker pipeline)
- internal retrieval / graph APIs
- SSE-based agent answers with grounded citations
- an evaluation harness and comparison UI

As of **2026-07-11**, the repository delivers a complete local vertical slice:

- a real indexing pipeline for Python repositories
- retrieval and graph lookup endpoints
- optional self-hosted embedding and reranker sidecars
- a working agent loop with 8 tools
- a frontend for indexing, querying, and baseline comparison
- a production-shaped Docker Compose package with static frontend serving

## Implemented System

### Indexing

- `git clone --depth=1`
- Python `ast` parse
- AST-boundary chunking for module docstrings, functions, classes, and methods
- chunk persistence with embedding cache
- optional real code embedding through the embedding sidecar
- graph rebuild with symbol definitions, module-level import edges, and best-effort intra-repo call edges

### Retrieval and Agent

- `/internal/search`
- sparse retrieval, dense retrieval hook, RRF fusion, and optional reranking
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
It should be treated as the committed baseline snapshot. It has not yet been
regenerated after enabling the real embedding/reranker sidecar path.

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
- Real embedding and reranker clients are implemented behind environment-driven sidecar boundaries.
- Graph coverage has moved beyond module imports with best-effort intra-repo call edges.
- `repo_id` isolation, caches, and internal-route protection are enforced in code and tests.
- The production packaging path is now explicit and locally smoke-tested.
- Groundedness stayed at the threshold floor for B4 (`0.95`), so citation verification is doing useful work.

## What Did Not Land

- a fresh full evaluation after real embedding/reranker enablement
- fully isolated B1/B2/B3/B4 retrieval implementations in the eval harness
- richer graph edges beyond best-effort calls, such as broader references and inheritance
- Judge / pairwise answer scoring
- production model-serving configuration for embedding/reranker
- public DNS / external demo availability

Those missing pieces explain why the current evaluation result should remain H1 unsupported.

## Recommended Next Steps

1. Re-index `requests` with `EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code` and `EMBEDDING_DIM=768`.
2. Re-run B1/B2/B3/B4 with the reranker enabled and write a new versioned result snapshot.
3. Separate dense-only, sparse-only, hybrid, and full-system retrieval paths in the eval harness.
4. Expand graph coverage for richer references and inheritance.
5. After retrieval quality is remeasured, finish Judge / pairwise scoring and public deployment.
