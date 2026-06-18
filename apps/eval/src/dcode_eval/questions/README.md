# Question set construction

Per [DESIGN.md §2.4.1](../../../../../docs/DESIGN.md), the evaluation question
set draws from three complementary sources:

| Source | Target size | Ground Truth |
|---|---|---|
| Manual annotation | 20–50 | Hand-labeled `(question, relevant chunks / files)` |
| Function reverse-synthesis | 30–50 | LLM generates a question that function X answers; function = GT |
| GitHub issue / commit mining | as available | Files referenced in the issue / commit = GT |

Total target: **50–80 questions**, *small and clean*.

## Current dataset

The repository currently includes a small versioned `requests` dataset at
`data/questions.jsonl`:

| Field | Current value |
|---|---|
| Repository | `requests` |
| Size | 16 questions |
| Source | manual |
| Taxonomy coverage | `L1`, `L2`, `L3` |
| Recorded outputs | `results/eval-suite/` |

This dataset is sufficient for a reproducible demo and for the current H1
snapshot. It is not yet large enough to be treated as a stable final benchmark.

## Taxonomy

Every question MUST carry one taxonomy label (DESIGN.md §2.4.2). The H1
hypothesis is checked primarily on the **L2 + L3** subset.

| Label | Reasoning scope |
|---|---|
| `L1` | Single-file factual (e.g. "What are the parameters of `Flask.run`?") |
| `L2` | Cross-file structural (e.g. "Who calls `validate_token`?") |
| `L3` | Architecture-level (e.g. "How is authentication wired end-to-end?") |

## Storage format

One JSON object per line in `data/questions.jsonl`:

```json
{
  "id": "q-001",
  "repo_id": "<uuid>",
  "question": "How does Flask register URL rules?",
  "taxonomy": "L2",
  "gt_chunk_ids": ["<uuid>", "<uuid>"],
  "gt_files": ["src/flask/app.py"],
  "source": "manual"
}
```

## Remaining work

- [ ] Expand `data/questions.jsonl` from 16 questions toward the 50-80 target
- [ ] Document the human-labeling protocol used for manual questions
- [ ] Lock per-source size targets instead of keeping them as ranges
- [ ] Hold-out subset for unbiased evaluation
