"""Mini-quiz at the end of each lesson."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class QuizView(QWidget):
    quiz_finished = Signal(int, int)  # score, total

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._questions: list[dict[str, Any]] = []
        self._index = 0
        self._score = 0
        self._option_buttons: list[QPushButton] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.setSpacing(16)

        self.header = QLabel("Mini Quiz")
        self.header.setObjectName("H1")
        outer.addWidget(self.header)

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("Dim")
        outer.addWidget(self.progress_label)

        self.card = QFrame()
        self.card.setObjectName("Card")
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(14)
        self.q_label = QLabel("")
        self.q_label.setObjectName("H2")
        self.q_label.setWordWrap(True)
        cl.addWidget(self.q_label)
        self.options_box = QVBoxLayout()
        self.options_box.setSpacing(8)
        cl.addLayout(self.options_box)

        self.feedback_label = QLabel("")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setObjectName("Dim")
        cl.addWidget(self.feedback_label)

        outer.addWidget(self.card)

        self.btn_next = QPushButton("Next ▶")
        self.btn_next.setObjectName("Primary")
        self.btn_next.setVisible(False)
        self.btn_next.clicked.connect(self._next_question)
        outer.addWidget(self.btn_next, 0, Qt.AlignRight)

        outer.addStretch(1)

    def start(self, questions: list[dict[str, Any]]) -> None:
        self._questions = questions or []
        self._index = 0
        self._score = 0
        if not self._questions:
            self.quiz_finished.emit(0, 0)
            return
        self._render()

    def _render(self) -> None:
        q = self._questions[self._index]
        self.progress_label.setText(f"Question {self._index + 1} of {len(self._questions)}")
        self.q_label.setText(q["q"])
        self.feedback_label.setText("")
        self.btn_next.setVisible(False)

        # clear options
        while self.options_box.count():
            it = self.options_box.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._option_buttons = []
        for i, opt in enumerate(q["options"]):
            btn = QPushButton(opt)
            btn.setObjectName("QuizOption")
            btn.setMinimumHeight(44)
            btn.clicked.connect(lambda _=False, idx=i: self._on_pick(idx))
            self.options_box.addWidget(btn)
            self._option_buttons.append(btn)

    def _on_pick(self, picked: int) -> None:
        q = self._questions[self._index]
        correct = int(q["answer"])
        for i, btn in enumerate(self._option_buttons):
            btn.setEnabled(False)
            if i == correct:
                btn.setObjectName("QuizOptionCorrect")
            elif i == picked:
                btn.setObjectName("QuizOptionWrong")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if picked == correct:
            self._score += 1
            self.feedback_label.setText("✅  " + q.get("explain", "Correct!"))
        else:
            self.feedback_label.setText("❌  " + q.get("explain", "Not quite. Re-read the lesson."))
        self.btn_next.setText("Finish quiz" if self._index == len(self._questions) - 1 else "Next ▶")
        self.btn_next.setVisible(True)

    def _next_question(self) -> None:
        if self._index >= len(self._questions) - 1:
            self.quiz_finished.emit(self._score, len(self._questions))
            return
        self._index += 1
        self._render()

    # ----------------------------------------------- voice helpers
    def pick_option_by_index(self, idx: int) -> None:
        """Voice command 'option two' etc. Picks an option if not yet answered."""
        if not self._option_buttons or idx < 0 or idx >= len(self._option_buttons):
            return
        if not self._option_buttons[0].isEnabled():
            # Already answered. Voice "next" should advance instead.
            return
        self._on_pick(idx)

    def advance_if_ready(self) -> None:
        if self.btn_next.isVisible():
            self._next_question()
