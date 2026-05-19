"""Clickable card for a lesson on the learning path."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pyquest.core.lesson_loader import Lesson


class LessonCard(QPushButton):
    activated = Signal(str)  # lesson_id

    def __init__(self, lesson: Lesson, locked: bool, completed: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.lesson = lesson
        self.setMinimumHeight(110)
        self.setCursor(Qt.PointingHandCursor)
        if completed:
            self.setObjectName("LessonCardDone")
        elif locked:
            self.setObjectName("LessonCardLocked")
        else:
            self.setObjectName("LessonCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(22)

        # Big italic serif chapter numeral
        order_label = QLabel(f"{lesson.order:02d}")
        if completed:
            num_color = "#D4B361"
        elif locked:
            num_color = "#5C5851"
        else:
            num_color = "#EEEAE0"
        order_label.setStyleSheet(
            f"font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            f"font-style: italic; font-size: 44px; color: {num_color};"
            f"letter-spacing: -2px;"
        )
        order_label.setFixedWidth(72)
        order_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        text_box = QVBoxLayout()
        text_box.setSpacing(6)
        title_text = lesson.title
        if lesson.coming_soon:
            title_text += "  · coming soon"
        title = QLabel(title_text)
        title.setStyleSheet(
            "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            "font-size: 22px; color: "
            + ("#928D7F" if locked else "#EEEAE0")
            + "; letter-spacing: -0.5px;"
        )
        sub = QLabel(lesson.objective or lesson.category)
        sub.setStyleSheet("color: #C4BFB1; font-size: 13px; line-height: 1.4;")
        sub.setWordWrap(True)
        text_box.addWidget(title)
        text_box.addWidget(sub)

        right_box = QVBoxLayout()
        right_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_box.setSpacing(6)
        if completed:
            status = QLabel("DONE")
            status.setObjectName("PillSuccess")
        elif locked:
            status = QLabel("LOCKED")
            status.setObjectName("Pill")
        elif lesson.coming_soon:
            status = QLabel("SOON")
            status.setObjectName("Pill")
        else:
            status = QLabel("START  →")
            status.setObjectName("PillAccent")
        xp = QLabel(f"+{lesson.xp_reward} XP")
        xp.setStyleSheet(
            "font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size: 11px; color: #D4B361; letter-spacing: 1px;"
        )
        right_box.addWidget(status, 0, Qt.AlignRight)
        right_box.addWidget(xp, 0, Qt.AlignRight)

        layout.addWidget(order_label)
        layout.addLayout(text_box, 1)
        layout.addLayout(right_box)

        self._locked = locked or lesson.coming_soon
        self.clicked.connect(self._on_click)

    def _on_click(self) -> None:
        if self._locked:
            return
        self.activated.emit(self.lesson.id)
