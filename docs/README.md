# Dcode Documentation Map

This folder is the documentation entry point for Dcode. New maintainers should start here, then read the English documents in `docs/en/` as the primary project references. Chinese copies live in `docs/ch/` for team handoff — treat them as **possibly-stale snapshots**: `docs/en/` is the single source of truth, so update English first.

> **Engineering backlog** (repo root, not this folder): the active improvement register and its changelog live at the top level — [`problem.md`](../problem.md) (open issues + phased improvement roadmap) and [`Improvement_Log.md`](../Improvement_Log.md) (completed items with commit refs).

## Folder Skeleton

```text
docs/
├── README.md                         documentation map and reading order
├── en/                               primary English documentation
│   ├── Technical_Design.md           architecture, service boundaries, data model, APIs
│   ├── Database.md                    database schema, Redis keys, SQL cookbook
│   ├── Project_Plan.md               goals, milestones, ownership, risks
│   ├── Repository_Structure.md       repository layout and module responsibilities
│   ├── Outstanding_Work.md           remaining work and known limits
│   ├── Sidecar_Smoke.md              real embedding/reranker smoke guide
│   ├── Agentic_Workflow.md           Claude Code, Codex, and Cursor workflow
│   └── Final_Report.md               implemented system, evaluation snapshot, and H1 decision
├── ch/                               Chinese counterparts for team handoff
│   ├── Technical_Design_ch.md
│   ├── Database_ch.md
│   ├── Project_Plan_ch.md
│   ├── Repository_Structure_ch.md
│   ├── Outstanding_Work_ch.md
│   ├── Sidecar_Smoke_ch.md
│   ├── Agentic_Workflow_ch.md
│   └── Final_Report_ch.md
└── archive/                          historical notes, not active guidance
    ├── 项目启动.md
    └── 执行路线.md
```

## Recommended Reading Order

1. [Repository_Structure.md](en/Repository_Structure.md): understand where each service and package lives.
2. [Technical_Design.md](en/Technical_Design.md): understand the architecture, API contracts, data model, retrieval path, graph path, and agent boundary.
3. [Database.md](en/Database.md): understand the persistence layer — schema, enums, indexes, Redis keyspace, write/read paths, and an SQL cookbook.
4. [Project_Plan.md](en/Project_Plan.md): understand goals, scope, ownership, priorities, and risks.
5. [Outstanding_Work.md](en/Outstanding_Work.md): see what still needs work before further evaluation or deployment.
6. [Sidecar_Smoke.md](en/Sidecar_Smoke.md): reproduce the real sidecar integration path before refreshing eval results.
7. [Final_Report.md](en/Final_Report.md): understand the recorded result snapshot and the H1 decision (with re-open criteria).
8. [Agentic_Workflow.md](en/Agentic_Workflow.md): understand how Claude Code, Codex, and Cursor were cross checked during development.

## Document Index

| English document | Chinese counterpart | Purpose |
|---|---|---|
| [Technical_Design.md](en/Technical_Design.md) | [Technical_Design_ch.md](ch/Technical_Design_ch.md) | Technical authority for architecture, components, data model, APIs, and NFRs |
| [Database.md](en/Database.md) | [Database_ch.md](ch/Database_ch.md) | Persistence reference: schema, enums, indexes, Redis keyspace, write/read paths, SQL cookbook |
| [Project_Plan.md](en/Project_Plan.md) | [Project_Plan_ch.md](ch/Project_Plan_ch.md) | Execution plan, ownership, milestones, priorities, risks, and decisions |
| [Repository_Structure.md](en/Repository_Structure.md) | [Repository_Structure_ch.md](ch/Repository_Structure_ch.md) | Current repository layout and service responsibilities |
| [Outstanding_Work.md](en/Outstanding_Work.md) | [Outstanding_Work_ch.md](ch/Outstanding_Work_ch.md) | Remaining work, known limits, deployment follow-ups |
| [Sidecar_Smoke.md](en/Sidecar_Smoke.md) | [Sidecar_Smoke_ch.md](ch/Sidecar_Smoke_ch.md) | Reproducible real embedding and reranker integration smoke |
| [Agentic_Workflow.md](en/Agentic_Workflow.md) | [Agentic_Workflow_ch.md](ch/Agentic_Workflow_ch.md) | How the team cross checked Claude Code, Codex, and Cursor |
| [Final_Report.md](en/Final_Report.md) | [Final_Report_ch.md](ch/Final_Report_ch.md) | Implemented system summary, evaluation snapshot, and the H1 decision |

## Archive

The `archive/` folder keeps historical planning notes. These files are useful for context, but they are not the active source of truth:

- [项目启动.md](archive/项目启动.md): original kickoff note.
- [执行路线.md](archive/执行路线.md): historical execution roadmap.

For current work, prefer the English documents in `docs/en/`, then consult the Chinese copies only when team handoff context is needed.
