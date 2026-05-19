"""Load lesson JSON files and badge definitions."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pyquest.config import BADGES_FILE, LESSONS_DIR


class LessonValidationError(ValueError):
    """Raised when a lesson JSON file is missing required fields or has bad types."""


@dataclass
class Lesson:
    id: str
    order: int
    title: str
    category: str
    xp_reward: int
    objective: str
    explanation_md: str
    example_code: str
    exercise_prompt: str
    starter_code: str
    hints: list[str]
    expected_output: str
    check: dict[str, Any]
    quiz: list[dict[str, Any]] = field(default_factory=list)
    coming_soon: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


# ---- validation ---------------------------------------------------------
REQUIRED_TOP = ("id", "order", "title")
VALID_CHECK_TYPES = {"none", "stdout_equals", "stdout_contains", "regex", "code_contains"}


def validate_lesson(data: dict[str, Any], source: str = "") -> None:
    """Raise LessonValidationError if the lesson dict is malformed.

    `source` is used in error messages so the user knows which file is broken.
    """
    where = f" in {source}" if source else ""

    if not isinstance(data, dict):
        raise LessonValidationError(f"Lesson{where} must be a JSON object, got {type(data).__name__}")

    for key in REQUIRED_TOP:
        if key not in data:
            raise LessonValidationError(f"Missing required field '{key}'{where}")

    if not isinstance(data["id"], str) or not data["id"]:
        raise LessonValidationError(f"'id' must be a non-empty string{where}")
    if not isinstance(data["order"], int):
        raise LessonValidationError(f"'order' must be an integer{where} (got {type(data['order']).__name__})")
    if not isinstance(data["title"], str) or not data["title"]:
        raise LessonValidationError(f"'title' must be a non-empty string{where}")

    # Optional types
    if "xp_reward" in data and not isinstance(data["xp_reward"], (int, float)):
        raise LessonValidationError(f"'xp_reward' must be a number{where}")
    if "hints" in data and not isinstance(data["hints"], list):
        raise LessonValidationError(f"'hints' must be a list{where}")
    if "quiz" in data and not isinstance(data["quiz"], list):
        raise LessonValidationError(f"'quiz' must be a list{where}")

    # check block
    check = data.get("check", {"type": "none"})
    if not isinstance(check, dict):
        raise LessonValidationError(f"'check' must be a JSON object{where}")
    ctype = check.get("type", "none")
    if ctype not in VALID_CHECK_TYPES:
        raise LessonValidationError(
            f"'check.type' = {ctype!r}{where} is unknown. "
            f"Expected one of: {sorted(VALID_CHECK_TYPES)}"
        )
    if ctype != "none" and "value" not in check:
        raise LessonValidationError(f"'check.value' is required when check.type='{ctype}'{where}")

    # quiz items
    for i, q in enumerate(data.get("quiz", [])):
        if not isinstance(q, dict):
            raise LessonValidationError(f"quiz[{i}] must be an object{where}")
        for key in ("q", "options", "answer"):
            if key not in q:
                raise LessonValidationError(f"quiz[{i}] missing '{key}'{where}")
        if not isinstance(q["options"], list) or len(q["options"]) < 2:
            raise LessonValidationError(f"quiz[{i}].options must be a list of 2+ items{where}")
        if not isinstance(q["answer"], int) or not (0 <= q["answer"] < len(q["options"])):
            raise LessonValidationError(
                f"quiz[{i}].answer must be an index into options (0..{len(q['options'])-1}){where}"
            )

    # warn on common typos: shadow keys that would silently be dropped
    KNOWN_KEYS = {
        "id", "order", "title", "category", "xp_reward", "objective",
        "explanation_md", "example_code", "exercise_prompt", "starter_code",
        "hints", "expected_output", "check", "quiz", "coming_soon",
    }
    SUSPECT = {
        "exp_reward": "xp_reward", "xpReward": "xp_reward",
        "explanation": "explanation_md", "exercise": "exercise_prompt",
        "starter": "starter_code", "expected": "expected_output",
        "tests": "check", "hint": "hints",
    }
    for key in data.keys():
        if key in KNOWN_KEYS:
            continue
        if key in SUSPECT:
            raise LessonValidationError(
                f"Unknown field '{key}'{where}. Did you mean '{SUSPECT[key]}'?"
            )


def _build_lesson(data: dict[str, Any], path: Path) -> Lesson:
    validate_lesson(data, source=path.name)
    return Lesson(
        id=data["id"],
        order=int(data["order"]),
        title=data["title"],
        category=data.get("category", "Basics"),
        xp_reward=int(data.get("xp_reward", 50)),
        objective=data.get("objective", ""),
        explanation_md=data.get("explanation_md", ""),
        example_code=data.get("example_code", ""),
        exercise_prompt=data.get("exercise_prompt", ""),
        starter_code=data.get("starter_code", ""),
        hints=list(data.get("hints", [])),
        expected_output=data.get("expected_output", ""),
        check=dict(data.get("check", {"type": "none"})),
        quiz=list(data.get("quiz", [])),
        coming_soon=bool(data.get("coming_soon", False)),
        raw=data,
    )


def load_lessons() -> list[Lesson]:
    lessons: list[Lesson] = []
    for path in sorted(LESSONS_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                raise LessonValidationError(
                    f"{path.name} is not valid JSON: {exc.msg} at line {exc.lineno}"
                ) from exc
        lessons.append(_build_lesson(data, path))
    lessons.sort(key=lambda lesson: lesson.order)
    return lessons


def load_badges() -> list[dict[str, Any]]:
    if not BADGES_FILE.exists():
        return []
    with BADGES_FILE.open("r", encoding="utf-8") as fh:
        return list(json.load(fh))
