#!/usr/bin/env python3
"""Regenerate every artifact that restates the evaluation numbers.

    python3 scripts/sync_eval_artifacts.py [--check] [results/eval-h1-bm25-2026-07-30]

Targets:
  - apps/frontend/src/demo/evalSnapshot.ts   (read by /methodology and the landing ladder)
  - marker-delimited blocks in README.md and docs/{en,ch}/Final_Report*.md

Why this exists. The same defect has been found three times: figures were
hand-copied into a document, then reality moved and the copy stayed. It hit
`evalSnapshot.ts` (numbers from a run that was never archived), the landing
ladder (decorative hardcoded bars), and README + Final_Report (stub-run numbers
left in place after the real-model run). A project whose whole claim is "we only
state what we can prove" cannot restate its own numbers by hand.

So every figure lives in exactly one place — the results directory — and
everything that displays it is generated from there. Prose carries qualitative
conclusions only ("H1 unsupported", "the corrected BM25 path is measured",
"the graph's contribution is unmeasured"); specific numbers belong inside a
generated block.

That claim only holds while this script is a pure function of the bytes under
the run directory. Taking a value from an mtime, the wall clock, or a constant
in here breaks it *without* breaking the check — the check would happily
compare two outputs of the same lie. See docs/en/Honesty_Constraints.md §11.

`--check` regenerates in memory and fails if any target is stale, so a future
re-run cannot silently desync the documentation. Wired into `make check`.

Markdown blocks are delimited like this, and the content between is replaced:

    <!-- BEGIN generated: eval-suite-metrics -->
    <!-- END generated: eval-suite-metrics -->

Files under docs/ch/ render with Chinese headers. Adding a block to a document
is just pasting the marker pair; this script needs no map of which document
contains what.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_RUN = "results/eval-h1-bm25-2026-07-30"
TS_OUT = ROOT / "apps/frontend/src/demo/evalSnapshot.ts"
DOC_TARGETS = [
    ROOT / "README.md",
    ROOT / "docs/en/Final_Report.md",
    ROOT / "docs/ch/Final_Report_ch.md",
]

BASELINES = ["B1", "B2", "B3", "B4"]
LEVELS = ["L1", "L2", "L3"]
H1_LEVELS = ["L2", "L3"]
# Architectural flows, deliberately clear of the corpus's credential-handling
# vocabulary (see CLAUDE.md on the environment's cyber safeguard).
DEMO_QUESTIONS = ["q-008", "q-010", "q-015", "q-016"]

TS_BASELINE_LABELS = {
    "B2": "Dense RAG",
    "B3": "Hybrid + rerank",
    "B4": "Dcode + graph + agent",
}

LABELS = {
    "en": {
        "B1": "BM25 sparse",
        "B2": "Dense RAG",
        "B3": "Hybrid + rerank",
        "B4": "Dcode (hybrid + call graph + agent)",
        "L1": "single-hop",
        "L2": "cross-file",
        "L3": "architecture",
        "baseline": "Baseline",
        "level": "Level",
        "grounded": "Groundedness",
        "below": "below the 0.95 guardrail",
        "cleared": "Cleared",
        "yes": "yes",
        "no": "no",
        "decision": "Decision",
        "rule": (
            "H1 is supported only if B4 beats **both** B2 and B3 by at least "
            "`{threshold}` composite points on **both** L2 and L3."
        ),
        "source": (
            "Source: `{path}` · verdict written {verdict_written} · {corpus} · k={k} · "
            "embedding {embedding} · reranker {reranker} · synthesis {synthesis}"
        ),
        # The word "recorded" was claiming trust it had not earned: the harness
        # writes no timestamp at all, so the date is reconstructed. Markdown has
        # room to say where from; the TypeScript snapshot keeps it to one line.
        "recovered": (
            "The date is **committed provenance, not harness output** — the harness "
            "writes no timestamp. Its observation basis and limits are recorded in "
            "`{path}provenance.json`."
        ),
    },
    "ch": {
        "B1": "BM25 稀疏检索",
        "B2": "稠密 RAG",
        "B3": "混合 + 重排",
        "B4": "Dcode（混合 + 调用图 + agent）",
        "L1": "单跳",
        "L2": "跨文件",
        "L3": "架构级",
        "baseline": "基线",
        "level": "层级",
        "grounded": "Groundedness",
        "below": "低于 0.95 护栏",
        "cleared": "是否达标",
        "yes": "是",
        "no": "否",
        "decision": "结论",
        "rule": (
            "仅当 B4 在 **L2 与 L3 上同时**比 B2 和 B3 都高出至少 `{threshold}` "
            "composite 分，H1 才算被支持。"
        ),
        "source": (
            "数据来源：`{path}` · 裁决写盘于 {verdict_written} · {corpus} · k={k} · "
            "embedding {embedding} · reranker {reranker} · 合成 {synthesis}"
        ),
        "recovered": (
            "该日期是**已提交的 provenance，而非 harness 输出** —— harness 完全不写"
            "时间戳。其观测依据与限制见 `{path}provenance.json`。"
        ),
    },
}

BLOCK_RE = re.compile(
    r"(<!-- BEGIN generated: (?P<name>[\w-]+) -->\n)(?P<body>.*?)(<!-- END generated: \2 -->)",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------


def load_run(run: pathlib.Path) -> dict:
    if not (run / "h1_report.json").exists():
        raise SystemExit(f"No h1_report.json under {run} — is that an eval results dir?")

    def read(rel: str) -> dict:
        return json.loads((run / rel).read_text())

    rows: dict[str, dict[str, dict]] = {}
    for baseline in BASELINES:
        per_question: dict[str, dict] = {}
        for line in (run / baseline / "per_question.jsonl").read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                per_question[record["question_id"]] = record
        rows[baseline] = per_question

    # The date used to be derived from h1_report.json's mtime. git does not
    # preserve mtimes, so that input changed on every clone and checkout: the
    # drift check was anchored to a value the repository cannot reproduce, and
    # regenerating on a fresh tree would have written the checkout date into the
    # artifacts as though it were the run's. A run that has been archived has a
    # date that will never move again, so it is safe to pin — see the
    # recovered-vs-recorded rule in docs/en/Honesty_Constraints.md.
    if not (run / "provenance.json").exists():
        raise SystemExit(
            f"No provenance.json under {run}.\n"
            "Run metadata must be committed bytes under the run directory — the "
            "generator may not read it from mtimes, the clock, or its own constants."
        )
    provenance = read("provenance.json")

    return {
        "suite": read("suite_summary.json"),
        "h1": read("h1_report.json"),
        "config": read("run_config.json"),
        "provenance": provenance,
        "display": provenance["display"],
        "groundedness_guardrail": float(provenance["groundedness_guardrail"]),
        "levels": {b: read(f"{b}/taxonomy_breakdown.json") for b in BASELINES},
        "rows": rows,
        "path": f"{run.relative_to(ROOT).as_posix()}/",
        # When the verdict file was written. Recorded in provenance outside the
        # harness — every surface that displays it has to preserve that distinction.
        "verdict_written": provenance["verdict_written_at"],
    }


def sparse_retrieval(run: dict) -> dict:
    """Return recorded config first, then explicitly recovered legacy metadata."""

    recorded = run["config"].get("sparse_retrieval")
    if isinstance(recorded, dict):
        return recorded
    recovered = run["provenance"].get("sparse_retrieval")
    if isinstance(recovered, dict):
        return recovered
    return {"implementation": "unrecorded"}


def baseline_label(run: dict, lang: str, baseline: str) -> str:
    if baseline != "B1":
        return str(LABELS[lang][baseline])

    implementation = sparse_retrieval(run).get("implementation")
    if implementation == "okapi_bm25_v1":
        return "BM25 sparse" if lang == "en" else "BM25 稀疏检索"
    if implementation == "legacy_ilike_weighted_substring":
        return "legacy lexical heuristic" if lang == "en" else "旧版词法启发式检索"
    return (
        "sparse retrieval (implementation unrecorded)" if lang == "en" else "稀疏检索（实现未记录）"
    )


def m3(value: object) -> str:
    return f"{float(value):.3f}"  # type: ignore[arg-type]


def signed3(value: object) -> str:
    number = float(value)  # type: ignore[arg-type]
    return f"+{number:.3f}" if number >= 0 else f"−{abs(number):.3f}"


# ---------------------------------------------------------------------------
# markdown blocks
# ---------------------------------------------------------------------------


def block_provenance(run: dict, lang: str) -> str:
    t = LABELS[lang]
    display = run["display"]
    source = t["source"].format(
        path=run["path"],
        verdict_written=run["verdict_written"],
        corpus=display["corpus"],
        k=run["config"]["k"],
        embedding=display["embedding"],
        reranker=display["reranker"],
        synthesis=display["synthesis"],
    )
    return f"{source}\n\n{t['recovered'].format(path=run['path'])}"


def block_suite_metrics(run: dict, lang: str) -> str:
    t = LABELS[lang]
    k = run["config"]["k"]
    lines = [
        f"| {t['baseline']} | Recall@{k} | MRR | nDCG@{k} | {t['grounded']} |",
        "|---|---:|---:|---:|---|",
    ]
    for baseline in BASELINES:
        row = run["suite"][baseline]
        grounded = m3(row["groundedness"])
        if row["groundedness"] < run["groundedness_guardrail"]:
            grounded = f"**{grounded}** ⚠️ {t['below']}"
        lines.append(
            f"| `{baseline}` {baseline_label(run, lang, baseline)} | "
            f"{m3(row['recall_at_k'])} | "
            f"{m3(row['mrr'])} | {m3(row['ndcg_at_k'])} | {grounded} |"
        )
    lines += ["", block_provenance(run, lang)]
    return "\n".join(lines)


def block_h1_verdict(run: dict, lang: str) -> str:
    t = LABELS[lang]
    h1 = run["h1"]
    lines = [
        f"**{t['decision']}: `{h1['decision']}`**",
        "",
        t["rule"].format(threshold=m3(h1["threshold"])),
        "",
        f"| {t['level']} | n | B2 | B3 | B4 | B4 vs B2 | B4 vs B3 | {t['cleared']} |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for level in H1_LEVELS:
        c = h1["comparisons"][level]
        lines.append(
            f"| `{level}` {t[level]} | {run['levels']['B4'][level]['questions']} | "
            f"{m3(c['B2_composite'])} | {m3(c['B3_composite'])} | {m3(c['B4_composite'])} | "
            f"{signed3(c['margin_vs_B2'])} | {signed3(c['margin_vs_B3'])} | "
            f"{t['yes'] if c['supported'] else t['no']} |"
        )
    return "\n".join(lines)


def block_level_ladder(run: dict, lang: str) -> str:
    t = LABELS[lang]
    k = run["config"]["k"]
    lines = [
        f"| {t['level']} | n | " + " | ".join(f"`{b}` Recall@{k}" for b in BASELINES) + " |",
        "|---|---:|" + "---:|" * len(BASELINES),
    ]
    for level in LEVELS:
        cells = " | ".join(m3(run["levels"][b][level]["recall_at_k"]) for b in BASELINES)
        lines.append(
            f"| `{level}` {t[level]} | {run['levels']['B4'][level]['questions']} | {cells} |"
        )
    return "\n".join(lines)


BLOCKS = {
    "eval-provenance": block_provenance,
    "eval-suite-metrics": block_suite_metrics,
    "eval-h1-verdict": block_h1_verdict,
    "eval-level-ladder": block_level_ladder,
}


def render_doc(path: pathlib.Path, run: dict) -> str:
    lang = "ch" if "/ch/" in path.as_posix() else "en"

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in BLOCKS:
            raise SystemExit(f"{path}: unknown generated block '{name}'")
        return f"{match.group(1)}\n{BLOCKS[name](run, lang)}\n\n{match.group(4)}"

    return BLOCK_RE.sub(replace, path.read_text())


# ---------------------------------------------------------------------------
# typescript snapshot
# ---------------------------------------------------------------------------


def render_ts(run: dict) -> str:
    out: list[str] = []
    w = out.append
    display = run["display"]

    def num(value: object) -> str:
        return repr(float(value))  # type: ignore[arg-type]

    def s(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    suite, h1, config, levels, rows = (
        run["suite"],
        run["h1"],
        run["config"],
        run["levels"],
        run["rows"],
    )

    w(f"""/**
 * H1 evaluation snapshot — generated from `{run["path"]}`, the full real-model run
 * ({display["embedding"]} + {display["reranker"]} + {display["synthesis"]})
 * against the {display["corpus"]} corpus. Verdict written {run["verdict_written"]} — a provenance
 * date, not one the harness recorded; see `{run["path"]}provenance.json`.
 *
 * Every number below is copied verbatim from a committed artifact in that
 * directory. Nothing here is rounded, adjusted, or hand-entered: `/methodology`
 * claims these match the recorded run, so they have to be checkable against it.
 *
 * Regenerate with `python3 scripts/sync_eval_artifacts.py` — do not edit by hand.
 */
""")

    w("export type BaselineName = 'B1' | 'B2' | 'B3' | 'B4';")
    w("/** Every question level in the suite. */")
    w("export type Level = 'L1' | 'L2' | 'L3';")
    w("/** The levels H1 is actually evaluated on — L1 is single-hop and out of scope. */")
    w("export type Taxonomy = 'L2' | 'L3';\n")
    w("/** Labels describe this recorded run, not every future implementation. */")
    w("export const baselineLabels: Record<BaselineName, string> = {")
    for baseline in BASELINES:
        label = (
            baseline_label(run, "en", baseline)
            if baseline == "B1"
            else TS_BASELINE_LABELS[baseline]
        )
        w(f"  {baseline}: {s(label)},")
    w("};\n")

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

    w("/** Where these numbers come from, so the page can point at it. */")
    w("export const snapshotSource = {")
    w(f"  path: '{run['path']}',")
    w("  /**")
    w("   * When the verdict file was written. Provenance metadata, not harness output —")
    w("   * the harness writes no timestamp, so every surface must preserve that distinction.")
    w(f"   * Observation basis and limits: `{run['path']}provenance.json`.")
    w("   */")
    w(f"  verdictWritten: '{run['verdict_written']}',")
    w(f"  corpus: {s(display['corpus'])},")
    w(f"  repoId: {s(config['repo_id_override'])},")
    w(f"  k: {config['k']},")
    w(f"  groundednessGuardrail: {num(run['groundedness_guardrail'])},")
    w(f"  sparseRetrieval: {json.dumps(sparse_retrieval(run), ensure_ascii=False)} as const,")
    for key in ("embedding", "reranker", "synthesis"):
        value = display[key]
        w(f"  {key}: '{value}',")
    w("} as const;\n")

    w("/** Whole-suite metrics, all 16 questions. */")
    w("export const suiteSummary: Record<BaselineName, BaselineSummary> = {")
    for baseline in BASELINES:
        row = suite[baseline]
        w(f"  {baseline}: {{")
        w(f"    baseline: '{baseline}',")
        w(f"    questions: {row['questions']},")
        w(f"    recallAtK: {num(row['recall_at_k'])},")
        w(f"    mrr: {num(row['mrr'])},")
        w(f"    ndcgAtK: {num(row['ndcg_at_k'])},")
        w(f"    groundedness: {num(row['groundedness'])},")
        w("  },")
    w("};\n")

    w("""/**
 * Per-level metrics. B3 and B4 are identical on every retrieval metric at every
 * level — B4's scored `retrieve()` calls the same hybrid search as B3, and its
 * call-graph tools fire later, inside the answer, which this harness does not
 * score. They diverge only on groundedness.
 */""")
    w("export const levelSummary: Record<Level, Record<BaselineName, BaselineSummary>> = {")
    for level in LEVELS:
        w(f"  {level}: {{")
        for baseline in BASELINES:
            row = levels[baseline][level]
            w(f"    {baseline}: {{")
            w(f"      baseline: '{baseline}',")
            w(f"      questions: {row['questions']},")
            w(f"      recallAtK: {num(row['recall_at_k'])},")
            w(f"      mrr: {num(row['mrr'])},")
            w(f"      ndcgAtK: {num(row['ndcg_at_k'])},")
            w(f"      groundedness: {num(row['groundedness'])},")
            w("    },")
        w("  },")
    w("};\n")

    w(f"/** Verbatim from {run['path']}h1_report.json. */")
    w("export const h1Report = {")
    w(f"  decision: {s(h1['decision'])},")
    w(f"  threshold: {num(h1['threshold'])},")
    w(f"  note: {s(h1['note'])},")
    w("  comparisons: {")
    for level in H1_LEVELS:
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

    w("""/**
 * Per-question transcripts, straight out of each baseline's per_question.jsonl.
 * Architectural flows chosen so the page doesn't lean on one narrow subsystem.
 */""")
    w("export const demoCases: DemoQuestionCase[] = [")
    for qid in DEMO_QUESTIONS:
        ref = rows["B3"][qid]
        w("  {")
        w(f"    questionId: {s(qid)},")
        w(f"    taxonomy: '{ref['taxonomy']}',")
        w(f"    question: {s(ref['question'])},")
        w(f"    gtFiles: {json.dumps(ref['gt_files'], ensure_ascii=False)},")
        w("    baselines: {")
        for baseline in BASELINES:
            row = rows[baseline][qid]
            w(f"      {baseline}: {{")
            w(f"        answer: {s(row['answer'])},")
            w(f"        citations: {json.dumps(row['citations'], ensure_ascii=False)},")
            w(f"        groundedness: {num(row['groundedness'])},")
            w(f"        recallAtK: {num(row['recall_at_k'])},")
            w(f"        mrr: {num(row['mrr'])},")
            w(f"        ndcgAtK: {num(row['ndcg_at_k'])},")
            w("      },")
        w("    },")
        w("  },")
    w("];")
    return "\n".join(out) + "\n"


def format_ts(source: str) -> str:
    """Return the generated snapshot in the frontend's locked Prettier format."""

    prettier = ROOT / "apps/frontend/node_modules/.bin/prettier"
    if not prettier.exists():
        raise SystemExit(
            "Frontend Prettier is not installed. Run `npm ci` in apps/frontend "
            "before synchronizing evaluation artifacts."
        )
    completed = subprocess.run(
        [str(prettier), "--stdin-filepath", str(TS_OUT)],
        input=source,
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    argv = sys.argv[1:]
    check = "--check" in argv
    positional = [arg for arg in argv if not arg.startswith("--")]
    run = load_run(ROOT / (positional[0] if positional else DEFAULT_RUN))

    targets: list[tuple[pathlib.Path, str]] = [(TS_OUT, format_ts(render_ts(run)))]
    targets += [(path, render_doc(path, run)) for path in DOC_TARGETS]
    stale = [path for path, rendered in targets if path.read_text() != rendered]

    if check:
        if stale:
            print("Evaluation artifacts are stale — they restate numbers that have moved:")
            for path in stale:
                print(f"  {path.relative_to(ROOT)}")
            print("\nRun: python3 scripts/sync_eval_artifacts.py")
            return 1
        print(f"Evaluation artifacts are in sync with {run['path']}")
        return 0

    for path, rendered in targets:
        path.write_text(rendered)
    print(f"Synced {len(targets)} artifact(s) from {run['path']}")
    for path in stale:
        print(f"  updated {path.relative_to(ROOT)}")

    print("\nsuite  recall  mrr    ndcg   grounded")
    for baseline in BASELINES:
        row = run["suite"][baseline]
        flag = (
            "  <- below guardrail"
            if row["groundedness"] < run["groundedness_guardrail"]
            else ""
        )
        print(
            f"  {baseline}  {row['recall_at_k']:.4f}  {row['mrr']:.4f}  "
            f"{row['ndcg_at_k']:.4f}  {row['groundedness']:.4f}{flag}"
        )
    print(f"\nH1: {run['h1']['decision']}")
    for level in H1_LEVELS:
        c = run["h1"]["comparisons"][level]
        print(
            f"  {level}: B4={c['B4_composite']:.4f} | vsB2={c['margin_vs_B2']:+.4f} "
            f"vsB3={c['margin_vs_B3']:+.4f} cleared={c['supported']}"
        )
    print("\nReminder: prose is NOT generated. Re-read the narrative copy in README.md,")
    print("docs/{en,ch}/Final_Report*.md and the /methodology page, and correct any")
    print("claim these numbers no longer support.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
