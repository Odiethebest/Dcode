# Dcode Outstanding Work

## Current Status

This document tracks remaining work after the implemented local vertical slice. It replaces the early skeleton task list and should be read with [Final_Report.md](Final_Report.md), [H1_Decision.md](H1_Decision.md), and [Sidecar_Smoke.md](Sidecar_Smoke.md).

Completed:

- indexing pipeline;
- internal retrieval API;
- LangGraph SSE agent path;
- eight registered agent tools;
- groundedness checks;
- frontend Index, Query, and Compare views;
- evaluation harness;
- embedding sidecar;
- reranker sidecar;
- production-shaped Compose packaging.

Verified in the recorded handoff:

- `make check`;
- `make frontend-build`;
- `make eval-smoke`;
- targeted agent graph and query SSE tests;
- local real-sidecar integration smoke.

The recorded H1 result remains **unsupported** on the checked-in evaluation suite.

## Retrieval Quality

- [x] Connect real chunk embeddings through the HTTP sidecar path.
- [x] Connect query-side embeddings for dense retrieval.
- [x] Connect the real reranker through the HTTP sidecar path.
- [x] Extend graph extraction beyond module imports with best-effort call edges.
- [x] Document the reproducible real-sidecar smoke flow.
- [ ] Re-index target repositories with real sidecars for final evaluation refresh.
- [ ] Expand graph extraction for richer references, inheritance, and complex attribute chains.

## Evaluation Completeness

- [ ] Connect judge and pairwise scoring.
- [ ] Expand the current 16-question `requests` suite.
- [ ] Produce stable B0 and B1 results under the same reporting format as B2, B3, and B4.
- [ ] Split baseline retrieval paths so B1, B2, B3, and B4 do not accidentally reuse the same `/internal/search` behavior.
- [ ] Regenerate `results/eval-suite/` with real embedding and reranker sidecars.
- [ ] Update frontend `evalSnapshot.ts` from the refreshed result files.

## External Deployment

- [ ] Configure real DNS for `dcode.odieyang.com`.
- [ ] Apply `.env.production` on the public host.
- [ ] Decide whether production Compose runs embedding and reranker sidecars or depends on external model services.
- [ ] Run production Compose and complete a public smoke test.

## Follow-Up Enhancements

- [ ] Reconsider LLM planner integration after retrieval quality is stable.
- [ ] Reconsider LLM synthesis after grounded retrieval quality is stable.
- [ ] Add OpenAPI type generation if frontend type drift becomes maintenance cost.
- [ ] Generate Compare page data from versioned evaluation snapshots if evaluation continues to change.

## Known Limits

- Default local environment still uses `EMBEDDING_MODEL=stub`.
- Graph v1 includes definitions, module import edges, and best-effort intra-repository call edges.
- The agent planner and synthesis path are rule-based, not LLM-driven.
- The current H1 decision does not include judge or pairwise metrics.
- The current H1 decision predates a full real-sidecar evaluation refresh.
