# Question set construction

Per [DESIGN.md §2.4.1](../../../../../docs/DESIGN.md), the evaluation question
set draws from three complementary sources:

| Source | Target size | Ground Truth |
|---|---|---|
| Manual annotation | 20–50 | Hand-labeled `(question, relevant chunks / files)` |
| Function reverse-synthesis | 30–50 | LLM generates a question that function X answers; function = GT |
| GitHub issue / commit mining | as available | Files referenced in the issue / commit = GT |

Total target: **50–80 questions**, *small and clean*.

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

## TODO (M3)

- [ ] Populate `data/questions.jsonl` with the curated set
- [ ] Document the human-labeling protocol used for the 20 manual questions
- [ ] Per-source size targets locked in (currently a range)
- [ ] Hold-out subset for unbiased evaluation
