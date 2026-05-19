"""Safe-ish code execution: subprocess + AST guard + timeout."""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass

from pyquest.config import EXEC_TIMEOUT_SECONDS
from pyquest.core.ast_guard import check_code


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    blocked: bool = False
    block_reason: str = ""

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.blocked


def _minimal_env() -> dict[str, str]:
    keep = ("SYSTEMROOT", "PATH", "PATHEXT", "TEMP", "TMP", "PYTHONIOENCODING")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_user_code(code: str, stdin_text: str = "") -> RunResult:
    guard = check_code(code)
    if not guard.ok:
        return RunResult(
            stdout="",
            stderr=f"[Sandbox] {guard.reason}",
            exit_code=-1,
            timed_out=False,
            blocked=True,
            block_reason=guard.reason,
        )

    # CREATE_NO_WINDOW only exists on Windows. Use getattr so the same code
    # works (with creationflags=0) on macOS and Linux.
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-c", code],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_minimal_env(),
            creationflags=creationflags,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return RunResult(stdout="", stderr=f"Could not start Python: {exc}", exit_code=-1, timed_out=False)

    timed_out = False
    try:
        stdout, stderr = proc.communicate(input=stdin_text, timeout=EXEC_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        timed_out = True
        stderr = (stderr or "") + (
            f"\n[Timed out after {EXEC_TIMEOUT_SECONDS}s. Possible infinite loop.]"
        )

    return RunResult(
        stdout=stdout or "",
        stderr=stderr or "",
        exit_code=proc.returncode if proc.returncode is not None else -1,
        timed_out=timed_out,
    )
