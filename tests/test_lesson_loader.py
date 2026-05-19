"""Tests for pyquest.core.lesson_loader.validate_lesson."""
import pytest

from pyquest.core.lesson_loader import LessonValidationError, validate_lesson


def _good() -> dict:
    return {
        "id": "01_x",
        "order": 1,
        "title": "Test lesson",
        "xp_reward": 50,
        "check": {"type": "stdout_equals", "value": "hi"},
        "quiz": [
            {"q": "?", "options": ["a", "b"], "answer": 1},
        ],
    }


def test_valid_lesson_ok():
    validate_lesson(_good(), source="01_x.json")


def test_missing_id():
    d = _good()
    del d["id"]
    with pytest.raises(LessonValidationError, match="id"):
        validate_lesson(d, source="x.json")


def test_missing_order():
    d = _good()
    del d["order"]
    with pytest.raises(LessonValidationError, match="order"):
        validate_lesson(d)


def test_bad_order_type():
    d = _good()
    d["order"] = "1"
    with pytest.raises(LessonValidationError, match="order"):
        validate_lesson(d)


def test_typo_xp_reward():
    d = _good()
    d.pop("xp_reward")
    d["exp_reward"] = 50
    with pytest.raises(LessonValidationError, match="xp_reward"):
        validate_lesson(d)


def test_typo_explanation():
    d = _good()
    d["explanation"] = "..."
    with pytest.raises(LessonValidationError, match="explanation_md"):
        validate_lesson(d)


def test_bad_check_type():
    d = _good()
    d["check"] = {"type": "not_a_thing"}
    with pytest.raises(LessonValidationError, match="check.type"):
        validate_lesson(d)


def test_check_missing_value():
    d = _good()
    d["check"] = {"type": "stdout_equals"}
    with pytest.raises(LessonValidationError, match="value"):
        validate_lesson(d)


def test_check_none_no_value_needed():
    d = _good()
    d["check"] = {"type": "none"}
    validate_lesson(d)  # should not raise


def test_quiz_missing_answer():
    d = _good()
    d["quiz"] = [{"q": "?", "options": ["a", "b"]}]
    with pytest.raises(LessonValidationError, match="answer"):
        validate_lesson(d)


def test_quiz_answer_out_of_range():
    d = _good()
    d["quiz"] = [{"q": "?", "options": ["a", "b"], "answer": 5}]
    with pytest.raises(LessonValidationError, match="answer"):
        validate_lesson(d)


def test_quiz_options_too_few():
    d = _good()
    d["quiz"] = [{"q": "?", "options": ["only one"], "answer": 0}]
    with pytest.raises(LessonValidationError, match="options"):
        validate_lesson(d)
