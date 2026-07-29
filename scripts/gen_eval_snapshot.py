#!/usr/bin/env python3
"""Regenerate apps/frontend/src/demo/evalSnapshot.ts from an eval results dir.

    python3 scripts/gen_eval_snapshot.py [results/eval-real]

/methodology and the landing baseline ladder both read the generated file, and
both state on the page that their numbers come from the results directory. That
claim only holds if the path from artifacts to UI is mechanical, so the snapshot
is generated rather than hand-entered — it has silently desynced before.

After regenerating: run `npx prettier --write` on the output, then `npm run
typecheck && npx vitest run` in apps/frontend. The page tests assert against the
snapshot rather than hardcoded literals, so they follow the data — but the
*prose* does not. Re-read the narrative copy on both surfaces and correct any
claim the new numbers no longer support.
"""

import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "results/eval-real")
OUT = ROOT / "apps/frontend/src/demo/evalSnapshot.ts"

BASELINES = ["B1", "B2", "B3", "B4"]
# Architectural flows, deliberately clear of the corpus's credential-handling
# vocabulary (see HANDOFF §7 on the environment's cyber safeguard).
DEMO_QUESTIONS = ["q-008", "q-010", "q-015", "q-016"]


def load(path):
    return json.loads((RUN / path).read_text())


def per_question(baseline):
    rows = {}
    for line in (RUN / baseline / "per_question.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["question_id"]] = r
    return rows


def num(x):
    """Emit floats verbatim — never round on the way in."""
    return repr(float(x))


def ts_str(s):
    return json.dumps(s, ensure_ascii=False)


suite = load("suite_summary.json")
h1 = load("h1_report.json")
run_config = load("run_config.json")
levels = {b: load(f"{b}/taxonomy_breakdown.json") for b in BASELINES}
rows = {b: per_question(b) for b in BASELINES}

RUN_DIR = f"{RUN.relative_to(ROOT).as_posix()}/"
# Recorded date = when the run wrote its verdict, not when this script ran.
RECORDED = datetime.date.fromtimestamp((RUN / "h1_report.json").stat().st_mtime).isoformat()
CORPUS = "psf/requests"
MODELS = {
    "embedding": "Jina v2-base-code (768-dim)",
    "reranker": "BGE reranker v2-m3",
    "synthesis": "gpt-4o-mini",
}

out = []
w = out.append

w(f"""/**
 * H1 evaluation snapshot — generated from `{RUN_DIR}`, the full real-model run
 * ({MODELS['embedding']} + {MODELS['reranker']} + {MODELS['synthesis']})
 * recorded {RECORDED} against the {CORPUS} corpus.
 *
 * Every number below is copied verbatim from a committed artifact in that
 * directory. Nothing here is rounded, adjusted, or hand-entered: `/methodology`
 * claims these match the recorded run, so they have to be checkable against it.
 *
 * Regenerate with `python3 scripts/gen_eval_snapshot.py` — do not edit by hand.
 */
""")

w("export type BaselineName = 'B1' | 'B2' | 'B3' | 'B4';")
w("/** Every question level in the suite. */")
w("export type Level = 'L1' | 'L2' | 'L3';")
w("/** The levels H1 is actually evaluated on — L1 is single-hop and out of scope. */")
w("export type Taxonomy = 'L2' | 'L3';\n")

w("""export interface BaselineSummary {
  baseline: BaselineName;
  questions: number;
  recallAtK: number;
  mrr: number;
  ndcgAtK: number;
  groundedness: number;
}

export interface H1Comparison {
  /** Questions at this level — L3 is n=3, small enough to be read with care. */
  questions: number;
  b2Composite: number;
  b3Composite: number;
  b4Composite: number;
  marginVsB2: number;
  marginVsB3: number;
  supported: boolean;
}

export interface DemoBaselineAnswer {
  answer: string;
  citations: string[];
  groundedness: number;
  recallAtK: number;
  mrr: number;
  ndcgAtK: number;
}

export interface DemoQuestionCase {
  questionId: string;
  taxonomy: Taxonomy;
  question: string;
  gtFiles: string[];
  baselines: Record<BaselineName, DemoBaselineAnswer>;
}
""")

# --- provenance -------------------------------------------------------------
w("/** Where these numbers come from, so the page can point at it. */")
w("export const snapshotSource = {")
w(f"  path: '{RUN_DIR}',")
w(f"  recorded: '{RECORDED}',")
w(f"  corpus: '{CORPUS}',")
w(f"  repoId: {ts_str(run_config['repo_id_override'])},")
w(f"  k: {run_config['k']},")
w(f"  embedding: '{MODELS['embedding']}',")
w(f"  reranker: '{MODELS['reranker']}',")
w(f"  synthesis: '{MODELS['synthesis']}',")
w("} as const;\n")

# --- suite summary ----------------------------------------------------------
w("/** Whole-suite metrics, all 16 questions. */")
w("export const suiteSummary: Record<BaselineName, BaselineSummary> = {")
for b in BASELINES:
    s = suite[b]
    w(f"  {b}: {{")
    w(f"    baseline: '{b}',")
    w(f"    questions: {s['questions']},")
    w(f"    recallAtK: {num(s['recall_at_k'])},")
    w(f"    mrr: {num(s['mrr'])},")
    w(f"    ndcgAtK: {num(s['ndcg_at_k'])},")
    w(f"    groundedness: {num(s['groundedness'])},")
    w("  },")
w("};\n")

# --- per-level summary ------------------------------------------------------
w("""/**
 * Per-level metrics. B3 and B4 are identical on every retrieval metric at every
 * level — B4's scored `retrieve()` calls the same hybrid search as B3, and its
 * call-graph tools fire later, inside the answer, which this harness does not
 * score. They diverge only on groundedness.
 */""")
w("export const levelSummary: Record<Level, Record<BaselineName, BaselineSummary>> = {")
for level in ["L1", "L2", "L3"]:
    w(f"  {level}: {{")
    for b in BASELINES:
        s = levels[b][level]
        w(f"    {b}: {{")
        w(f"      baseline: '{b}',")
        w(f"      questions: {s['questions']},")
        w(f"      recallAtK: {num(s['recall_at_k'])},")
        w(f"      mrr: {num(s['mrr'])},")
        w(f"      ndcgAtK: {num(s['ndcg_at_k'])},")
        w(f"      groundedness: {num(s['groundedness'])},")
        w("    },")
    w("  },")
w("};\n")

# --- h1 report --------------------------------------------------------------
w("/** Verbatim from results/eval-real/h1_report.json. */")
w("export const h1Report = {")
w(f"  decision: {ts_str(h1['decision'])},")
w(f"  threshold: {num(h1['threshold'])},")
w(f"  note: {ts_str(h1['note'])},")
w("  comparisons: {")
for level in ["L2", "L3"]:
    c = h1["comparisons"][level]
    w(f"    {level}: {{")
    w(f"      questions: {levels['B4'][level]['questions']},")
    w(f"      b2Composite: {num(c['B2_composite'])},")
    w(f"      b3Composite: {num(c['B3_composite'])},")
    w(f"      b4Composite: {num(c['B4_composite'])},")
    w(f"      marginVsB2: {num(c['margin_vs_B2'])},")
    w(f"      marginVsB3: {num(c['margin_vs_B3'])},")
    w(f"      supported: {'true' if c['supported'] else 'false'},")
    w("    },")
w("  } satisfies Record<Taxonomy, H1Comparison>,")
w("};\n")

# --- transcripts ------------------------------------------------------------
w("""/**
 * Per-question transcripts, straight out of each baseline's per_question.jsonl.
 * Architectural flows chosen so the page doesn't lean on one narrow subsystem.
 */""")
w("export const demoCases: DemoQuestionCase[] = [")
for qid in DEMO_QUESTIONS:
    ref = rows["B3"][qid]
    w("  {")
    w(f"    questionId: {ts_str(qid)},")
    w(f"    taxonomy: '{ref['taxonomy']}',")
    w(f"    question: {ts_str(ref['question'])},")
    w(f"    gtFiles: {json.dumps(ref['gt_files'], ensure_ascii=False)},")
    w("    baselines: {")
    for b in BASELINES:
        r = rows[b][qid]
        w(f"      {b}: {{")
        w(f"        answer: {ts_str(r['answer'])},")
        w(f"        citations: {json.dumps(r['citations'], ensure_ascii=False)},")
        w(f"        groundedness: {num(r['groundedness'])},")
        w(f"        recallAtK: {num(r['recall_at_k'])},")
        w(f"        mrr: {num(r['mrr'])},")
        w(f"        ndcgAtK: {num(r['ndcg_at_k'])},")
        w("      },")
    w("    },")
    w("  },")
w("];")

OUT.write_text("\n".join(out) + "\n")

# Verification digest — metrics only, no transcript bodies.
print("wrote", OUT.relative_to(ROOT))
print("\nsuite  recall  mrr    ndcg   grounded")
for b in BASELINES:
    s = suite[b]
    print(f"  {b}  {s['recall_at_k']:.4f}  {s['mrr']:.4f}  {s['ndcg_at_k']:.4f}  {s['groundedness']:.4f}")
print("\nlevel ladder (recall@5)")
for level in ["L1", "L2", "L3"]:
    cells = "  ".join(f"{b}={levels[b][level]['recall_at_k']:.4f}" for b in BASELINES)
    print(f"  {level} (n={levels['B4'][level]['questions']})  {cells}")
print("\nH1")
for level in ["L2", "L3"]:
    c = h1["comparisons"][level]
    print(
        f"  {level}: B2={c['B2_composite']:.4f} B3={c['B3_composite']:.4f} "
        f"B4={c['B4_composite']:.4f} | vsB2={c['margin_vs_B2']:+.4f} "
        f"vsB3={c['margin_vs_B3']:+.4f} supported={c['supported']}"
    )
print(
    "\ngroundedness by level (B4):",
    {lvl: round(levels["B4"][lvl]["groundedness"], 4) for lvl in ["L1", "L2", "L3"]},
)
print("demo cases:", DEMO_QUESTIONS)
