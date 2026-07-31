# Question set construction

Per the
[Technical Design question-set contract](../../../../../docs/en/Technical_Design.md#question-set-construction),
the evaluation question set draws from three complementary sources:

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
| Size | 33 questions |
| Source | 16 `manual` + 17 `graph_reverse` |
| Taxonomy coverage | `L1` 5 · `L2` 16 · `L3` 12 |
| Recorded outputs | `results/eval-h1-bm25-2026-07-30/` was measured on the original 16 only |

This dataset is sufficient for a reproducible demo and for a Requests-only
pre-registered re-test. It is not yet large enough to be treated as a stable
final benchmark, and it is a single corpus, so nothing measured on it
generalises.

### The `graph_reverse` expansion (q-017 – q-033)

17 questions — 8 cross-file `L2` and 9 architecture `L3` — added to bring `L3`
from 3 to 12, which was the pre-registered precondition for a graph-sensitive H1
re-run. Every anchor was verified to resolve 1:1 against the live `psf/requests`
index before any baseline was run.

`source: graph_reverse` records **how they were built: reverse-constructed from
the indexed call relationships and source of the current corpus.** That label
exists so the construction method travels with the data, because it carries a
known bias that a reader must be able to see:

> A suite derived from the graph the system itself produced cannot contain a
> flow that graph misses. The documented blind spots — no type inference,
> unresolved inherited `self.method()` calls — are therefore absent from these
> questions by construction, and that absence favours `B4`. The bias is
> recorded rather than corrected; see
> [`docs/en/Final_Report.md`](../../../../../docs/en/Final_Report.md).

Ground truth is stored as `gt_targets` anchors only, never as chunk uuids, so the
batch survives a re-index. Known properties, measured rather than asserted:

- all 17 span ≥ 2 files (up to 5), unlike 4 of the original 8 `L2` questions;
- maximum pairwise GT overlap within the batch is 0.33, and 0.33 against the
  original 16 — compared with 1.00 / 0.75 / 0.50 among the pre-existing
  `L2`/`L3` pairs, which are retained unchanged for historical comparability;
- 7 ground-truth chunks are 2–5 line exception-class declarations, which are
  close to invisible to dense retrieval, so q-019 / q-024 / q-031 / q-032 are
  hard for every baseline;
- the `Response` class chunk used by q-023 and q-028 is 453 lines, large enough
  that lexical retrieval may hit it on almost any related term.

The last two were identified and accepted before the run, not discovered in the
results.

## Taxonomy

Every question MUST carry one taxonomy label; see the
[H1 decision contract](../../../../../docs/en/Technical_Design.md#h1-decision-and-additional-gates).
The H1 hypothesis is checked on the **L2 + L3** subsets.

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
  "gt_targets": [
    {
      "file_path": "src/flask/app.py",
      "symbol_name": "add_url_rule",
      "start_line": 1210
    }
  ],
  "gt_files": ["src/flask/app.py"],
  "source": "manual"
}
```

`gt_chunk_ids` are index-specific and exist for backwards compatibility with
recorded snapshots. New or regenerated eval runs should prefer `gt_targets`,
which are stable anchors based on source location. When the CLI is run with
`--repo-id <current_repo_uuid>`, the harness resolves each target against the
current `chunks` table and computes retrieval metrics from the resolved chunk
ids.

## Remaining work

- [x] Expand `data/questions.jsonl` from 16 to 33 questions (`L3` 3 → 12)
- [ ] Continue toward the 50-80 target with a **second corpus** (the indexed
      `encode/httpx`), not with more Requests questions — padding one repository
      produces restatements of the same flows. Reaching `L3` ≈ 22 is what pushes
      a single question's weight below the 0.05 H1 margin; at `L3` = 12 one
      question still moves the level composite by up to 8.3%.
- [ ] Bind each question to its own repository before mixing corpora:
      `dcode_eval.run` records a single `repo_id_override` and reads one
      `index_revision`, so the corpus-revision guard is single-repo today
- [ ] Document the human-labeling protocol used for manual questions
- [ ] Lock per-source size targets instead of keeping them as ranges
- [ ] Hold-out subset for unbiased evaluation
