"""Read-only console for stdout/stderr."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


class ConsoleView(QPlainTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Console")
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 11))
        self.setPlaceholderText("Output will appear here when you click Run.")

    def append_text(self, text: str, color: str | None = None) -> None:
        if not text:
            return
        cursor = self.textCursor()
        fmt = QTextCharFormat()
        if color:
            fmt.setForeground(QColor(color))
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text, fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def reset(self) -> None:
        self.clear()
