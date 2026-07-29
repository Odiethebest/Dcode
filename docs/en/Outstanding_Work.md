# Dcode Outstanding Work

## Current Status

This document tracks remaining work after the implemented local vertical slice. It replaces the early skeleton task list and should be read with [Final_Report.md](Final_Report.md) and [Sidecar_Smoke.md](Sidecar_Smoke.md).

> The granular, code-level backlog now lives in [`problem.md`](../../problem.md) (open issues; completed items in [`Improvement_Log.md`](../../Improvement_Log.md)). This document keeps the milestone-level view of remaining work.

Completed:

- indexing pipeline;
- internal retrieval API;
- LangGraph SSE agent path;
- eight registered agent tools;
- groundedness checks;
- the `/workbench` exploration surface, plus `/` and `/methodology`;
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

The recorded H1 result remains **unsupported**, now measured on a full real-model
run (`results/eval-real/`) rather than the earlier stub snapshot. The obstacle is
no longer muted baselines: B4's scored retrieval is the same call as B3's, so the
call graph is never scored. See [Final_Report.md](Final_Report.md) for the numbers,
the diagnosis, and the criteria that would re-open the question.

## Retrieval Quality

- [x] Connect real chunk embeddings through the HTTP sidecar path.
- [x] Connect query-side embeddings for dense retrieval.
- [x] Connect the real reranker through the HTTP sidecar path.
- [x] Extend graph extraction beyond module imports with best-effort call edges.
- [x] Document the reproducible real-sidecar smoke flow.
- [ ] Re-index target repositories with real sidecars for final evaluation refresh.
- [ ] Expand graph extraction for richer references, inheritance, and complex attribute chains.

## Evaluation Completeness

- [x] Run the suite under real embedding + reranker — `results/eval-real/` (2026-07-28).
- [x] Produce B1 under the same reporting format as B2/B3/B4.
- [x] Generate every displayed figure from the results directory, with `make check` failing on drift.
- [ ] **Score B4 on its final verified evidence set** — the correction that would let the call graph reach the metrics at all. Criteria set 2, item 1 in [Final_Report.md](Final_Report.md).
- [ ] **Expand L3 beyond n=3** (target ~12), human-reviewed before the re-run.
- [ ] Connect judge and pairwise scoring — still a stub, so pairwise win-rate is `null` and that acceptance threshold is unmeasured.
- [ ] Produce a stable B0 result, or keep reporting it as **not measured** (needs an API token).
- [ ] Investigate B4's groundedness dip at the source — the agent emitting citations that fail verification. Do **not** address it by changing how the score is computed.
- [ ] Add a second corpus. One repository supports no claim about generality.

## External Deployment

- [ ] Configure real DNS for `dcode.odieyang.com`.
- [ ] Apply `.env.production` on the public host.
- [ ] Decide whether production Compose runs embedding and reranker sidecars or depends on external model services.
- [ ] Run production Compose and complete a public smoke test.

## Follow-Up Enhancements

- [ ] Reconsider LLM planner integration after retrieval quality is stable.
- [x] LLM answer synthesis — opt-in OpenAI, token-streamed, citation-whitelisted to groundedness 1.0 (2026-07-27).
- [ ] Add OpenAPI type generation if frontend type drift becomes maintenance cost.
- [ ] Restore accessibility live regions in the rebuilt workbench — a regression against a previously closed item; details and the design question in `CLAUDE.md`.

## Known Limits

- Default local environment still uses `EMBEDDING_MODEL=stub`.
- Graph v1 includes definitions, module import edges, and best-effort intra-repository call edges.
- The agent planner is rule-based; answer synthesis is optional LLM (OpenAI; default `stub` keeps the rule-based template).
- The current H1 decision does not include judge or pairwise metrics.
- The current H1 decision predates a full real-sidecar evaluation refresh.
