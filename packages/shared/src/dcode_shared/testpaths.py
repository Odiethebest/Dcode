"""One rule for what counts as test code, shared by every service.

Indexing keeps tests: they are part of the repository and someone will
legitimately ask about them. Retrieval is where they hurt. Asked "how does
Requests turn cookies into a Cookie header", a code-understanding tool that
answers with `test_requests.py` has not answered the question — the
implementation is the answer, and a test is at best evidence that the
implementation behaves.

This was not a theoretical concern. On the 2026-07-31 suite, **47% of retrieved
candidates and between 26% and 48% of cited evidence came from `tests/`** across
every arm.

The rule is binary on purpose. A tunable "tests are worth 0.7 of a real file"
weight would be a hyper-parameter, and one fitted on an evaluation set whose
ground truth happens to contain no test files at all — see
`docs/en/Final_Report.md` on why that direction is not available here.
"""

from pathlib import PurePosixPath

_TEST_DIR_NAMES = {"test", "tests", "testing"}


def is_test_path(file_path: str) -> bool:
    """True when a repository path is test code by ordinary Python convention."""
    path = PurePosixPath(file_path)
    if any(part.lower() in _TEST_DIR_NAMES for part in path.parts[:-1]):
        return True
    name = path.name.lower()
    if name == "conftest.py":
        return True
    return name.startswith("test_") or name.endswith("_test.py")


def query_is_about_tests(query: str) -> bool:
    """True when the asker is asking about tests, so tests are the right answer.

    Deliberately generous: excluding test code from someone who asked for it is
    a worse failure than including it for someone who did not.
    """
    normalized = query.lower()
    return any(
        marker in normalized
        for marker in ("test", "spec", "fixture", "conftest", "测试", "用例")
    )
