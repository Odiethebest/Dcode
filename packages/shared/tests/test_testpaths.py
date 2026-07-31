"""Test-code detection, shared by retrieval and the eval harness."""

import pytest
from dcode_shared.testpaths import is_test_path, query_is_about_tests


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_requests.py",
        "tests/conftest.py",
        "test/helpers.py",
        "src/pkg/test_utils.py",
        "src/pkg/utils_test.py",
        "a/testing/thing.py",
    ],
)
def test_recognises_test_code(path: str) -> None:
    assert is_test_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/requests/sessions.py",
        "src/requests/adapters.py",
        # A module about protests is not a test module, and `latest.py` does not
        # end in `_test.py`. Substring matching would get both wrong.
        "src/pkg/protest.py",
        "src/pkg/latest.py",
        "src/contest/models.py",
    ],
)
def test_does_not_overmatch_ordinary_source(path: str) -> None:
    assert not is_test_path(path)


def test_a_question_about_tests_keeps_them() -> None:
    # Withholding test code from someone who asked for it is the worse failure.
    assert query_is_about_tests("How is redirect handling tested?")
    assert query_is_about_tests("哪些测试覆盖了 cookie 持久化？")
    assert not query_is_about_tests("How does Requests persist cookies?")
