"""Dashboard: greeting, big stats, continue-learning CTA, badges grid."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pyquest.core.lesson_loader import Lesson
from pyquest.core.progress import Progress


def _stat_card(title: str, value: str, sub: str) -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    card.setMinimumHeight(120)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 18, 20, 16)
    layout.setSpacing(6)
    # Mono uppercase label
    t = QLabel(title.upper())
    t.setStyleSheet(
        "font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
        "font-size: 10px; color: #928D7F; letter-spacing: 3px;"
    )
    # Big serif numeral
    v = QLabel(value)
    v.setObjectName("H1")
    v.setStyleSheet(
        "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
        "font-size: 48px; color: #EEEAE0; letter-spacing: -2px; line-height: 1;"
    )
    s = QLabel(sub)
    s.setStyleSheet("color: #928D7F; font-size: 12px;")
    layout.addWidget(t)
    layout.addWidget(v)
    layout.addStretch(1)
    layout.addWidget(s)
    return card


class DashboardPage(QWidget):
    continue_clicked = Signal(str)  # next lesson id
    open_path = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(44, 36, 44, 40)
        outer.setSpacing(14)

        # Eyebrow date label (mono uppercase, gold)
        self.eyebrow = QLabel("TODAY · A GOOD DAY TO CODE")
        self.eyebrow.setObjectName("Eyebrow")
        outer.addWidget(self.eyebrow)

        # Display headline (serif)
        self.greet = QLabel("Welcome back. Today is a good day to code.")
        self.greet.setObjectName("H1")
        self.greet.setWordWrap(True)
        self.greet.setStyleSheet(
            "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            "font-size: 44px; color: #EEEAE0; letter-spacing: -1px; line-height: 1.05;"
        )
        outer.addWidget(self.greet)

        self.tag = QLabel(
            "Pick up where you stopped, or wander the chapter index. "
            "Your streak is alive; five minutes is enough to keep it."
        )
        self.tag.setStyleSheet("color: #C4BFB1; font-size: 15px; line-height: 1.5;")
        self.tag.setWordWrap(True)
        outer.addWidget(self.tag)
        outer.addSpacing(8)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        self.card_xp = _stat_card("Experience", "0", "Total XP")
        self.card_level = _stat_card("Level", "1", "Keep climbing")
        self.card_streak = _stat_card("Streak", "0 🔥", "Come back daily")
        self.card_done = _stat_card("Lessons done", "0", "Out of 10")
        for c in (self.card_xp, self.card_level, self.card_streak, self.card_done):
            stats_row.addWidget(c, 1)
        outer.addLayout(stats_row)

        # Continue card (hero)
        cont = QFrame()
        cont.setObjectName("Card")
        cont.setStyleSheet(
            "QFrame#Card { background-color: #23201D; border: 1px solid #454039; border-radius: 18px; }"
        )
        cl = QHBoxLayout(cont)
        cl.setContentsMargins(32, 28, 32, 28)
        cl.setSpacing(24)
        text_box = QVBoxLayout()
        text_box.setSpacing(6)
        self.cont_eyebrow = QLabel("RESUME · YOUR PATH")
        self.cont_eyebrow.setObjectName("Eyebrow")
        self.cont_title = QLabel("Continue learning")
        self.cont_title.setStyleSheet(
            "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            "font-size: 32px; color: #EEEAE0; letter-spacing: -1px; line-height: 1.05;"
        )
        self.cont_title.setWordWrap(True)
        self.cont_sub = QLabel("Pick up where you left off.")
        self.cont_sub.setStyleSheet("color: #C4BFB1; font-size: 14px; line-height: 1.5;")
        self.cont_sub.setWordWrap(True)
        text_box.addWidget(self.cont_eyebrow)
        text_box.addWidget(self.cont_title)
        text_box.addWidget(self.cont_sub)
        cl.addLayout(text_box, 1)
        self.btn_continue = QPushButton("Resume chapter  →")
        self.btn_continue.setObjectName("Primary")
        self.btn_path = QPushButton("View path")
        self.btn_path.setObjectName("Ghost")
        cl.addWidget(self.btn_path)
        cl.addWidget(self.btn_continue)
        outer.addWidget(cont)

        # Badges section
        badge_h = QLabel("Badges")
        badge_h.setObjectName("H2")
        outer.addWidget(badge_h)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.badge_host = QWidget()
        self.badge_grid = QGridLayout(self.badge_host)
        self.badge_grid.setSpacing(12)
        scroll.setWidget(self.badge_host)
        outer.addWidget(scroll, 1)

        self.btn_path.clicked.connect(self.open_path.emit)
        self._next_lesson_id: str | None = None
        self.btn_continue.clicked.connect(self._on_continue)

    def _on_continue(self) -> None:
        if self._next_lesson_id:
            self.continue_clicked.emit(self._next_lesson_id)
        else:
            self.open_path.emit()

    def refresh(self, progress: Progress, lessons: list[Lesson], badges: list[dict]) -> None:
        completed = progress.completed_lesson_ids()
        active_lessons = [lesson for lesson in lessons if not lesson.coming_soon]
        done_count = sum(1 for lesson in active_lessons if lesson.id in completed)

        self.card_xp.findChild(QLabel, "H1").setText(str(progress.xp))
        self.card_level.findChild(QLabel, "H1").setText(str(progress.level))
        self.card_streak.findChild(QLabel, "H1").setText(f"{progress.streak} 🔥")
        # Subtitle on the streak card now reflects freeze count.
        freezes = progress.streak_freezes
        if freezes > 0:
            self.card_streak.findChildren(QLabel)[2].setText(
                f"❄ {freezes} freeze{'s' if freezes != 1 else ''} saved"
            )
        else:
            self.card_streak.findChildren(QLabel)[2].setText("Come back daily")
        self.card_done.findChild(QLabel, "H1").setText(f"{done_count}")
        self.card_done.findChildren(QLabel)[2].setText(f"Out of {len(active_lessons)}")

        # Next lesson = first non-completed, non-coming-soon
        nxt = next((lesson for lesson in active_lessons if lesson.id not in completed), None)
        if nxt:
            self._next_lesson_id = nxt.id
            self.cont_title.setText(f"Lesson {nxt.order}: {nxt.title}")
            self.cont_sub.setText(nxt.objective or "Tap start to begin.")
            self.btn_continue.setText("▶ Start lesson")
        else:
            self._next_lesson_id = None
            self.cont_title.setText("All lessons complete 🎉")
            self.cont_sub.setText("More lessons coming soon!")
            self.btn_continue.setText("Review lessons")

        # Rebuild badges grid
        for i in reversed(range(self.badge_grid.count())):
            w = self.badge_grid.itemAt(i).widget()
            if w:
                w.deleteLater()
        earned = progress.earned_badge_ids()
        for idx, badge in enumerate(badges):
            row, col = divmod(idx, 4)
            chip = QFrame()
            chip.setObjectName("Card")
            chip.setMinimumHeight(110)
            cl = QVBoxLayout(chip)
            cl.setContentsMargins(14, 12, 14, 12)
            icon = QLabel(badge.get("icon", "🏅"))
            icon.setStyleSheet("font-size: 26px;")
            name = QLabel(badge["name"])
            name.setObjectName("H3")
            desc = QLabel(badge.get("description", ""))
            desc.setObjectName("Dim")
            desc.setWordWrap(True)
            cl.addWidget(icon)
            cl.addWidget(name)
            cl.addWidget(desc)
            if badge["id"] not in earned:
                chip.setStyleSheet("QFrame#Card { opacity: 0.4; }")
                icon.setText("🔒")
            self.badge_grid.addWidget(chip, row, col)
