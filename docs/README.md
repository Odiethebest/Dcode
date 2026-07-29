# Dcode Documentation Map

Documentation entry point. `docs/en/` is the single source of truth; `docs/ch/`
holds Chinese counterparts for team handoff — treat those as **possibly-stale
snapshots** and update English first.

## Reviewing this project — three steps

If you are here to evaluate the work rather than extend it, read in this order.
It takes about fifteen minutes and answers the question the project is built
around: *is the claim true, and can you check it?*

**1. [`../README.md`](../README.md) — what it is and what it claims.**
The hypothesis (H1), the architecture, the baseline ladder, and the recorded
result. Every figure there is generated from `results/eval-real/`.

**2. [`en/Final_Report.md`](en/Final_Report.md) — the verdict.**
H1 is recorded **unsupported**. This document gives the numbers, states plainly
which findings did hold (hybrid retrieval is validated; the call graph's
contribution is *unmeasured* rather than absent), discloses that B4's groundedness
falls below its own pre-registered guardrail, and sets the criteria that would
re-open the question. It also records the previous set of criteria and what
happened when they were met.

**3. Run it and use it.** Startup is three commands — see
[Real Model Mode](../README.md#real-model-mode); `make up` alone gives a healthy
API whose every query dies at the embedding step. Then index a repository in the
workbench, ask a cross-file question, and **click a citation**: that opens the
real indexed source at the cited line and lets you walk the call graph from
there. That interaction is the product. `/methodology` shows the same evaluation
as step 2, read from the same generated snapshot.

Then, depending on what you want to check:

- **How it is built** → [`en/Technical_Design.md`](en/Technical_Design.md), then
  [`en/Repository_Structure.md`](en/Repository_Structure.md) and
  [`en/Database.md`](en/Database.md).
- **Whether the UI's claims are disciplined** →
  [`en/Honesty_Constraints.md`](en/Honesty_Constraints.md). The rules governing
  what the interface may assert, each with its reason. Probably the most
  distinctive engineering content here.
- **What is unfinished** → [`en/Final_Report.md`](en/Final_Report.md#outstanding-work),
  including known regressions.
- **Reproducing the real-model path** → [`en/Sidecar_Smoke.md`](en/Sidecar_Smoke.md).
- **How it was developed** → [`en/Agentic_Workflow.md`](en/Agentic_Workflow.md).

## Folder Skeleton

```text
docs/
├── README.md                     this map
├── en/                           primary English documentation
│   ├── Final_Report.md           implemented system, evaluation, H1 decision, re-open criteria
│   ├── Honesty_Constraints.md    what the UI may claim, and why — most rules are test-pinned
│   ├── Technical_Design.md       architecture, service boundaries, data model, APIs
│   ├── Database.md               schema, Redis keys, write/read paths, SQL cookbook
│   ├── Repository_Structure.md   repository layout and module responsibilities
│   ├── Project_Plan.md           goals, milestones, ownership, risks
│   ├── Sidecar_Smoke.md          reproducible real embedding/reranker path
│   └── Agentic_Workflow.md       how Claude Code, Codex, and Cursor were cross checked
├── ch/                           Chinese counterparts (possibly stale)
└── archive/                      historical records — not current guidance
    ├── problem.md                development-era code-level problem register (to 2026-07)
    ├── Improvement_Log.md        its changelog of completed items
    ├── frontend-redesign-brief.md  the executed brief behind the workbench rebuild
    ├── 项目启动.md                original kickoff note
    └── 执行路线.md                historical execution roadmap
```

## Document Index

| English | Chinese | Purpose |
|---|---|---|
| [Final_Report.md](en/Final_Report.md) | [Final_Report_ch.md](ch/Final_Report_ch.md) | Implemented system, evaluation snapshot, H1 decision, iteration history, re-open criteria |
| [Honesty_Constraints.md](en/Honesty_Constraints.md) | — | Rules governing what the UI may claim, with reasoning |
| [Technical_Design.md](en/Technical_Design.md) | [Technical_Design_ch.md](ch/Technical_Design_ch.md) | Architecture, components, data model, APIs, NFRs |
| [Database.md](en/Database.md) | [Database_ch.md](ch/Database_ch.md) | Schema, enums, indexes, Redis keyspace, SQL cookbook |
| [Repository_Structure.md](en/Repository_Structure.md) | [Repository_Structure_ch.md](ch/Repository_Structure_ch.md) | Repository layout and service responsibilities |
| [Project_Plan.md](en/Project_Plan.md) | [Project_Plan_ch.md](ch/Project_Plan_ch.md) | Execution plan, ownership, milestones, risks, decisions |
| [Sidecar_Smoke.md](en/Sidecar_Smoke.md) | [Sidecar_Smoke_ch.md](ch/Sidecar_Smoke_ch.md) | Real embedding and reranker integration smoke |
| [Agentic_Workflow.md](en/Agentic_Workflow.md) | [Agentic_Workflow_ch.md](ch/Agentic_Workflow_ch.md) | How the team cross checked Claude Code, Codex, and Cursor |

## Elsewhere in the repository

- [`../results/README.md`](../results/README.md) — four recorded evaluation runs
  and which one is the current conclusion. Read before citing any number.
- [`../design/README.md`](../design/README.md) — the two HTML prototypes the UI
  was built from. Open them in a browser; they remain the visual authority.
- [`../CLAUDE.md`](../CLAUDE.md) — operational notes for agent sessions: current
  state, environment gotchas, working agreements. Tooling configuration rather
  than project documentation.
