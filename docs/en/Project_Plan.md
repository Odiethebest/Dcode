# Dcode Project Plan

## Purpose

This document defines the execution plan for Dcode: goals, scope, acceptance criteria, priorities, ownership, milestones, risks, and closed decisions. Technical architecture is covered in [Technical_Design.md](Technical_Design.md).

## Goals

| Goal | Description |
|---|---|
| O1 | Quantitatively evaluate H1 on a controlled code-understanding benchmark |
| O2 | Build a working local vertical slice for repository indexing, retrieval, graph lookup, and agent answers |
| O3 | Deliver a frontend demo that shows indexing, querying, citations, and evaluation comparison |
| O4 | Keep the system reproducible through documented commands, committed fixtures, and versioned results |

## Core Hypothesis

H1 states that hybrid retrieval plus static code structure improves repository question answering over flat similarity retrieval, especially for relationship-heavy L2 and L3 questions.

The main baseline ladder is:

1. GitHub Search.
2. BM25.
3. Vanilla dense RAG.
4. Hybrid sparse plus dense retrieval.
5. Hybrid retrieval plus graph structure.

The system is useful only if improvements are visible in reproducible metrics and supported by grounded code citations.

## Scope

In scope:

- Python repository indexing;
- sparse retrieval and optional dense retrieval;
- optional cross-encoder reranking;
- static symbol and graph extraction;
- internal retrieval and graph APIs;
- agent tool orchestration and SSE output;
- grounded citations;
- local Docker Compose operation;
- evaluation harness and comparison UI.

Out of scope for the first complete slice:

- multi-language parsing beyond Python;
- full dynamic call graph precision;
- production-scale multi-tenant hardening;
- complete LLM judge automation;
- hosted model infrastructure beyond local sidecars.

## Acceptance Criteria

The project is considered complete enough for the course deliverable when:

- `make check` passes;
- local Docker Compose services are healthy;
- a target repository can be indexed end to end;
- `/internal/search` and graph routes return usable results;
- `/api/v1/query` streams grounded answers;
- evaluation results are committed under `results/`;
- the H1 decision is documented with supporting metrics;
- known limitations are explicitly recorded.

## Ownership

| Owner | Area |
|---|---|
| Ziqi (Odie) Yang | Technical lead, indexing pipeline, agent orchestration, integration, documentation |
| Yuxin(Lacey)Liang | Retrieval stack, embedding and reranker integration, graph stack contributions |
| Yufan Li | Evaluation workflow, frontend, demo and result presentation |

## Milestones

| Milestone | Target outcome |
|---|---|
| M0 | Repository skeleton, workspace, Docker stack, initial schema, and health checks |
| M1 | Minimal indexing pipeline and internal search |
| M2 | Graph lookup and agent tool path |
| M3 | Evaluation harness and frontend demo |
| M4 | Real sidecar integration, documentation, final report, and handoff |

## Priority Order

The priority order is strict:

1. H1-critical retrieval and evaluation work.
2. Agent integration on stable internal APIs.
3. Frontend and demo polish.
4. Deployment and production-shaped packaging.
5. Nice-to-have planner, synthesis, and UI enhancements.

If time is limited, the platform should degrade to a smaller but reproducible evaluation path rather than a broader but unverified system.

## Current Status

As of the latest documented handoff:

- indexing, retrieval, graph lookup, agent SSE, frontend, and evaluation harness exist;
- real embedding and reranker sidecars are wired;
- the internal API contract remained stable through sidecar integration;
- the checked-in H1 result remains unsupported on the current recorded suite;
- a fresh real-model evaluation remains follow-up work.

## Risk Register

| Risk | Mitigation |
|---|---|
| Retrieval quality does not improve H1 | Keep metrics falsifiable and report unsupported results honestly |
| Graph coverage misses dynamic Python behavior | Document limits and classify them as static-analysis coverage gaps |
| Sidecar configuration drifts from DB vector dimension | Record `EMBEDDING_DIM` and rebuild DB volumes when changing dimensions |
| Baselines accidentally share the same retrieval path | Split baseline implementations before final eval refresh |
| Frontend numbers drift from result files | Generate or manually verify snapshots from committed `results/` |
| Deployment cannot be completed in time | Preserve local reproducibility and production-shaped compose files |

## Closed Decisions

| Decision | Outcome |
|---|---|
| Primary language | Python repository indexing first |
| Backend framework | FastAPI services with shared schemas |
| Graph extraction | Python `ast` based v1 graph |
| Dense model path | Optional HTTP embedding sidecar |
| Reranker path | Optional HTTP reranker sidecar |
| Public query response | SSE stream through the API gateway |
| Groundedness | Required answer verification step |

## Handoff Notes

Future work should begin from the current main branch, run the sidecar smoke in [Operations.md](Operations.md), and then refresh the evaluation suite with the same model configuration. Any H1 update should cite the exact result directory and question set version.
