"""Auto-check engine for lesson exercises."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class CheckResult:
    passed: bool
    feedback: str


def _normalize(text: str, strip: bool, case_sensitive: bool) -> str:
    if strip:
        text = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not case_sensitive:
        text = text.lower()
    return text


def check_exercise(check: dict[str, Any], code: str, stdout: str, stderr: str) -> CheckResult:
    """Evaluate the lesson's check spec against the user's run.

    Supported types:
      - stdout_equals   {value, strip?, case_sensitive?}
      - stdout_contains {value, case_sensitive?}
      - regex           {value}
      - code_contains   {value, case_sensitive?}
      - none            (concept lessons; always passes)
    """
    if stderr.strip() and check.get("type") != "none":
        return CheckResult(False, "Your code produced an error. Read the message in the console and try again.")

    ctype = check.get("type", "none")

    if ctype == "none":
        return CheckResult(True, "Concept understood — let's move on!")

    if ctype == "stdout_equals":
        expected = check["value"]
        strip = check.get("strip", True)
        case_sensitive = check.get("case_sensitive", True)
        if _normalize(stdout, strip, case_sensitive) == _normalize(expected, strip, case_sensitive):
            return CheckResult(True, "Output matches exactly.")
        return CheckResult(False, f"Expected output:\n{expected}\n\nYour output:\n{stdout or '(nothing)'}")

    if ctype == "stdout_contains":
        expected = check["value"]
        case_sensitive = check.get("case_sensitive", True)
        haystack = stdout if case_sensitive else stdout.lower()
        needle = expected if case_sensitive else expected.lower()
        if needle in haystack:
            return CheckResult(True, "Looks good — your output includes what we expected.")
        return CheckResult(False, f"Your output should contain: {expected!r}")

    if ctype == "regex":
        pattern = check["value"]
        if re.search(pattern, stdout, re.MULTILINE):
            return CheckResult(True, "Output matches the expected pattern.")
        return CheckResult(False, "Output didn't match the expected pattern. Re-read the hint.")

    if ctype == "code_contains":
        expected = check["value"]
        case_sensitive = check.get("case_sensitive", False)
        hay = code if case_sensitive else code.lower()
        needle = expected if case_sensitive else expected.lower()
        if needle in hay:
            return CheckResult(True, "Nice — your code uses what we expected.")
        return CheckResult(False, f"Your code should use: {expected}")

    return CheckResult(False, f"Unknown check type: {ctype}")
