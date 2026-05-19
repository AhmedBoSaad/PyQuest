"""Tests for pyquest.core.checker."""
from pyquest.core.checker import check_exercise


def test_none_always_passes():
    r = check_exercise({"type": "none"}, code="", stdout="", stderr="")
    assert r.passed


def test_none_does_not_fail_on_stderr():
    r = check_exercise({"type": "none"}, code="", stdout="", stderr="oops")
    assert r.passed


def test_stderr_fails_other_check_types():
    r = check_exercise(
        {"type": "stdout_equals", "value": "hi"}, code="", stdout="hi", stderr="boom"
    )
    assert not r.passed


def test_stdout_equals_strict_match():
    r = check_exercise(
        {"type": "stdout_equals", "value": "Hello", "strip": True, "case_sensitive": True},
        code="", stdout="Hello\n", stderr=""
    )
    assert r.passed


def test_stdout_equals_case_mismatch():
    r = check_exercise(
        {"type": "stdout_equals", "value": "Hello", "case_sensitive": True},
        code="", stdout="hello", stderr=""
    )
    assert not r.passed


def test_stdout_equals_case_insensitive_passes():
    r = check_exercise(
        {"type": "stdout_equals", "value": "Hello", "case_sensitive": False},
        code="", stdout="hello", stderr=""
    )
    assert r.passed


def test_stdout_contains():
    r = check_exercise(
        {"type": "stdout_contains", "value": "world"},
        code="", stdout="hello world!", stderr=""
    )
    assert r.passed


def test_stdout_contains_missing():
    r = check_exercise(
        {"type": "stdout_contains", "value": "moon"},
        code="", stdout="hello world!", stderr=""
    )
    assert not r.passed


def test_regex_matches():
    r = check_exercise(
        {"type": "regex", "value": r"\d{3}"},
        code="", stdout="number: 123", stderr=""
    )
    assert r.passed


def test_regex_no_match():
    r = check_exercise(
        {"type": "regex", "value": r"\d{5,}"},
        code="", stdout="number: 12", stderr=""
    )
    assert not r.passed


def test_code_contains_case_insensitive_by_default():
    r = check_exercise(
        {"type": "code_contains", "value": "FOR"},
        code="for i in range(3): print(i)", stdout="", stderr=""
    )
    assert r.passed


def test_unknown_check_type():
    r = check_exercise({"type": "nonsense"}, code="", stdout="", stderr="")
    assert not r.passed
    assert "Unknown" in r.feedback


def test_strip_handles_trailing_whitespace_and_newlines():
    r = check_exercise(
        {"type": "stdout_equals", "value": "x", "strip": True},
        code="", stdout="x   \n\n", stderr=""
    )
    assert r.passed
