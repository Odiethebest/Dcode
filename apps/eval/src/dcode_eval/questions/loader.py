"""JSONL loader for curated eval questions."""

import json
from pathlib import Path

from dcode_eval.questions.models import EvalQuestion


def load_questions(path: str | Path) -> list[EvalQuestion]:
    data_path = Path(path)
    return [
        EvalQuestion.model_validate(json.loads(line))
        for line in data_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
