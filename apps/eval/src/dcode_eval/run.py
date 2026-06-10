"""Evaluation CLI entry — implements DESIGN.md §2.4 + §4.4.

Usage:
    uv run python -m dcode_eval.run \
        --baseline B4 \
        --questions data/questions.jsonl \
        --output results/run-001/

TODO(M3): wire baseline lookup + per-question iteration + metric aggregation
+ result file emission per DESIGN.md §4.4.
"""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dcode-eval", description="Dcode evaluation harness")
    parser.add_argument(
        "--baseline",
        required=True,
        choices=["B0", "B1", "B2", "B3", "B4"],
        help="DESIGN.md §2.4.3 baseline tier to run",
    )
    parser.add_argument(
        "--questions",
        required=True,
        help="Path to questions JSONL (see apps/eval/src/dcode_eval/questions/README.md)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for per_question.jsonl / metrics.json / taxonomy_breakdown.json",
    )
    args = parser.parse_args(argv)

    print(f"[skeleton] baseline={args.baseline}")
    print(f"[skeleton] questions={args.questions}")
    print(f"[skeleton] output={args.output}")
    print("[skeleton] real eval pipeline lands at M3 per DESIGN.md §2.4 + §4.4.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
