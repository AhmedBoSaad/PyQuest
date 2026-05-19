"""Vertical learning path: list of lesson cards, sequentially unlocked."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from pyquest.core.lesson_loader import Lesson
from pyquest.core.progress import Progress
from pyquest.ui.widgets.lesson_card import LessonCard


class LearningPathPage(QWidget):
    lesson_chosen = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(44, 36, 44, 40)
        outer.setSpacing(8)

        eyebrow = QLabel("THE PATH")
        eyebrow.setObjectName("Eyebrow")
        outer.addWidget(eyebrow)
        outer.addSpacing(4)

        title = QLabel("Chapters")
        title.setStyleSheet(
            "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            "font-size: 44px; color: #EEEAE0; letter-spacing: -2px; line-height: 1.05;"
        )
        outer.addWidget(title)

        sub = QLabel("Fifteen chapters in order. Finish one to unlock the next.")
        sub.setStyleSheet("color: #C4BFB1; font-size: 15px; line-height: 1.5;")
        outer.addWidget(sub)
        outer.addSpacing(16)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.host = QWidget()
        self.host_layout = QVBoxLayout(self.host)
        self.host_layout.setSpacing(10)
        self.host_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.host)
        outer.addWidget(self.scroll, 1)

    def refresh(self, lessons: list[Lesson], progress: Progress) -> None:
        # clear
        while self.host_layout.count():
            it = self.host_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        completed = progress.completed_lesson_ids()
        unlocked_seen = False
        for lesson in lessons:
            done = lesson.id in completed
            # Unlock if previous active lesson is complete (or this is the first)
            if lesson.coming_soon:
                locked = True
            elif done:
                locked = False
            elif not unlocked_seen:
                locked = False
                unlocked_seen = True
            else:
                locked = True
            card = LessonCard(lesson, locked=locked, completed=done, parent=self.host)
            card.activated.connect(self.lesson_chosen.emit)
            self.host_layout.addWidget(card)
        self.host_layout.addStretch(1)
