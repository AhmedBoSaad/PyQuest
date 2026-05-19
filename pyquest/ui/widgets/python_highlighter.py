"""Minimal Python syntax highlighter."""
from __future__ import annotations

import keyword

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)

        kw_fmt = _fmt("#C792EA", bold=True)
        builtin_fmt = _fmt("#82AAFF")
        string_fmt = _fmt("#C3E88D")
        number_fmt = _fmt("#F78C6C")
        comment_fmt = _fmt("#637777", italic=True)
        decorator_fmt = _fmt("#FFCB6B")
        function_fmt = _fmt("#82AAFF")

        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        for kw in keyword.kwlist:
            self.rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))

        builtins = (
            "print input len range int float str list dict tuple set bool "
            "type abs min max sum sorted reversed enumerate zip map filter "
            "open round True False None"
        ).split()
        for b in builtins:
            self.rules.append((QRegularExpression(rf"\b{b}\b"), builtin_fmt))

        self.rules.append((QRegularExpression(r"\bdef\s+(\w+)"), function_fmt))
        self.rules.append((QRegularExpression(r"@\w+"), decorator_fmt))
        self.rules.append((QRegularExpression(r"\b\d+(\.\d+)?\b"), number_fmt))
        self.rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_fmt))
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_fmt))
        self.rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))

    def highlightBlock(self, text: str) -> None:
        for regex, fmt in self.rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
