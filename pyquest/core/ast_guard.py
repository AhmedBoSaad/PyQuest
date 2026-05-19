"""AST-based safety check for user-submitted code.

This is a *learning* sandbox, not a security boundary. Goals:
  - Stop accidental damage (file deletion, network calls).
  - Stop confusing imports that wouldn't help a beginner anyway.
  - Allow normal beginner code (print, input, loops, lists, etc.).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass

BLOCKED_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "pathlib", "ctypes",
    "multiprocessing", "threading", "pickle", "marshal", "shelve",
    "requests", "urllib", "http", "ftplib", "smtplib", "telnetlib",
    "importlib", "tempfile", "asyncio", "fcntl", "winreg", "msvcrt",
    "builtins", "__builtin__",
}

BLOCKED_CALLS = {
    "eval", "exec", "compile", "__import__", "open",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "breakpoint",
}

# Bare names that are themselves dangerous (no attribute access needed).
BLOCKED_NAMES = {"__builtins__", "__loader__", "__spec__", "__package__"}

# Allowed dunders. Everything else dunder is blocked.
ALLOWED_DUNDERS = {"__name__", "__doc__", "__main__"}


@dataclass
class GuardResult:
    ok: bool
    reason: str = ""


class _Guard(ast.NodeVisitor):
    def __init__(self) -> None:
        self.problem: str | None = None

    def _flag(self, msg: str) -> None:
        if self.problem is None:
            self.problem = msg

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in BLOCKED_MODULES:
                self._flag(f"Importing '{alias.name}' is blocked in this learning sandbox.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        top = (node.module or "").split(".")[0]
        if top in BLOCKED_MODULES:
            self._flag(f"Importing from '{node.module}' is blocked in this learning sandbox.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in BLOCKED_CALLS:
            self._flag(f"Calling '{func.id}()' is blocked in this learning sandbox.")
        if isinstance(func, ast.Attribute) and func.attr.startswith("__"):
            self._flag(f"Calling dunder method '{func.attr}' is blocked.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") and node.attr not in ALLOWED_DUNDERS:
            self._flag(f"Accessing '{node.attr}' is blocked.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in BLOCKED_NAMES:
            self._flag(f"Accessing '{node.id}' is blocked in this learning sandbox.")
        elif node.id.startswith("__") and node.id.endswith("__") and node.id not in ALLOWED_DUNDERS:
            self._flag(f"Accessing '{node.id}' is blocked.")
        self.generic_visit(node)


def check_code(code: str) -> GuardResult:
    """Return GuardResult.ok=True if the code is allowed, else with a friendly reason."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Let the actual interpreter produce the syntax-error message; don't block here.
        return GuardResult(ok=True)

    guard = _Guard()
    guard.visit(tree)
    if guard.problem:
        return GuardResult(ok=False, reason=guard.problem)
    return GuardResult(ok=True)
