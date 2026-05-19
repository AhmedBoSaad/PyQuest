"""Main window: sidebar + topbar + stacked pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pyquest.config import APP_NAME
from pyquest.core.lesson_loader import Lesson, load_badges, load_lessons
from pyquest.core.progress import Progress
from pyquest.services.tts import get_narrator
from pyquest.ui.pages.dashboard import DashboardPage
from pyquest.ui.pages.learning_path import LearningPathPage
from pyquest.ui.pages.lesson_view import LessonView
from pyquest.ui.pages.settings_view import SettingsPage
from pyquest.ui.widgets.badge_popup import BadgePopup
from pyquest.ui.widgets.xp_bar import XPBar


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Learn Python")
        self.resize(1280, 820)
        self.setMinimumSize(1024, 720)

        self.progress = Progress()
        self.lessons: list[Lesson] = load_lessons()
        self.badges = load_badges()
        self._lessons_by_id = {lesson.id: lesson for lesson in self.lessons}

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----- Sidebar -----
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(14, 22, 14, 16)
        sl.setSpacing(2)

        # Brand block: serif π glyph + name + subtitle (editorial masthead).
        brand_box = QWidget()
        brand_row = QHBoxLayout(brand_box)
        brand_row.setContentsMargins(4, 0, 4, 22)
        brand_row.setSpacing(8)
        brand_mark = QLabel("π")
        brand_mark.setStyleSheet(
            "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            "font-size: 30px; font-style: italic; color: #D4B361;"
        )
        brand_name = QLabel(APP_NAME)
        brand_name.setStyleSheet(
            "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            "font-size: 22px; color: #EEEAE0;"
        )
        brand_row.addWidget(brand_mark)
        brand_row.addWidget(brand_name)
        brand_row.addStretch(1)
        # Separator line below brand
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #3D3933;")
        sl.addWidget(brand_box)
        sl.addWidget(sep)
        sl.addSpacing(14)

        # Section eyebrow
        section_label = QLabel("WORKSHOP")
        section_label.setStyleSheet(
            "font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size: 9px; color: #928D7F; letter-spacing: 3px;"
            "padding: 4px 10px 8px;"
        )
        sl.addWidget(section_label)

        self.btn_dash = self._nav_button("Dashboard")
        self.btn_path = self._nav_button("Chapters")
        self.btn_lesson = self._nav_button("Current chapter")
        self.btn_settings = self._nav_button("Settings")
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for b in (self.btn_dash, self.btn_path, self.btn_lesson, self.btn_settings):
            b.setCheckable(True)
            self.nav_group.addButton(b)
            sl.addWidget(b)
        self.btn_dash.setChecked(True)
        self.btn_lesson.setEnabled(False)

        sl.addStretch(1)

        # Foot tip in editorial style
        tip = QLabel("Five minutes is enough to keep the streak.")
        tip.setStyleSheet("color: #928D7F; font-size: 11.5px; padding: 12px 10px 0;")
        tip.setWordWrap(True)
        sl.addWidget(tip)
        root.addWidget(sidebar)

        # ----- Right column: topbar + stack -----
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(64)
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(24, 12, 24, 12)
        self.xp_bar = XPBar()
        tl.addWidget(self.xp_bar, 1)
        right_col.addWidget(topbar)

        self.stack = QStackedWidget()
        right_col.addWidget(self.stack, 1)

        self.dashboard = DashboardPage()
        self.learning_path = LearningPathPage()
        self.lesson_view = LessonView()
        self.settings_view = SettingsPage()
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.learning_path)
        self.stack.addWidget(self.lesson_view)
        self.stack.addWidget(self.settings_view)

        right_wrap = QWidget()
        right_wrap.setLayout(right_col)
        root.addWidget(right_wrap, 1)

        # ----- Wire up -----
        self.btn_dash.clicked.connect(lambda: self._goto(0))
        self.btn_path.clicked.connect(lambda: self._goto(1))
        self.btn_lesson.clicked.connect(lambda: self._goto(2))
        self.btn_settings.clicked.connect(lambda: self._goto(3))

        self.dashboard.continue_clicked.connect(self._open_lesson)
        self.dashboard.open_path.connect(lambda: self._goto(1))
        self.learning_path.lesson_chosen.connect(self._open_lesson)
        self.lesson_view.back_to_path.connect(lambda: self._goto(1))
        self.lesson_view.lesson_completed.connect(self._on_lesson_completed)
        self.lesson_view.next_lesson_requested.connect(self._on_next_lesson_requested)

        self._refresh_all()
        # Show the welcome wizard on first launch (once).
        # Use a short timer so the main window appears first, then the modal
        # opens on top of it — feels much smoother than a wizard before paint.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(150, self._maybe_show_wizard)

    def _maybe_show_wizard(self) -> None:
        if self.progress.first_run_done:
            return
        self.show_welcome_wizard()

    def show_welcome_wizard(self) -> None:
        from pyquest.ui.widgets.welcome_wizard import WelcomeWizard
        wiz = WelcomeWizard(self)
        wiz.exec()
        # Mark done regardless of how they closed it (skip is OK — Settings has the same options).
        self.progress.mark_first_run_done()
        self._refresh_all()

    # ----------------------------------------------------- helpers
    def _nav_button(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("NavItem")
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(38)
        return b

    def _goto(self, idx: int) -> None:
        # Stop narration + clear any pending yes/no callback if leaving the lesson.
        if self.stack.currentIndex() == 2 and idx != 2:
            get_narrator().stop()
            self.lesson_view._clear_pending_yes()
        self.stack.setCurrentIndex(idx)
        # Keep nav button check in sync
        for i, btn in enumerate((self.btn_dash, self.btn_path, self.btn_lesson, self.btn_settings)):
            btn.setChecked(i == idx)

    def closeEvent(self, event) -> None:  # noqa: N802
        get_narrator().stop()
        super().closeEvent(event)

    def _refresh_all(self) -> None:
        self.dashboard.refresh(self.progress, self.lessons, self.badges)
        self.learning_path.refresh(self.lessons, self.progress)
        self.xp_bar.update_state(
            level=self.progress.level,
            xp_into=self.progress.xp_into_level,
            xp_for_next=self.progress.xp_for_next_level,
            streak=self.progress.streak,
        )

    def _open_lesson(self, lesson_id: str) -> None:
        lesson = self._lessons_by_id.get(lesson_id)
        if not lesson:
            return
        self.lesson_view.load_lesson(lesson)
        self.btn_lesson.setEnabled(True)
        self._goto(2)

    def _on_next_lesson_requested(self) -> None:
        """Advance to the next available lesson; otherwise return to the path."""
        current = getattr(self.lesson_view, "_lesson", None)
        if current is None:
            self._goto(1)
            return
        # Find next non-coming-soon lesson with order > current.
        candidates = [
            lesson for lesson in self.lessons
            if lesson.order > current.order and not lesson.coming_soon
        ]
        if candidates:
            self._open_lesson(candidates[0].id)
        else:
            # No more lessons — back to the learning path.
            self._goto(1)

    def _on_lesson_completed(self, lesson_id: str, xp: int, quiz_score: int, quiz_total: int) -> None:
        was_already_done = self.progress.is_completed(lesson_id)
        self.progress.mark_completed(lesson_id, quiz_score=quiz_score, quiz_total=quiz_total)
        if not was_already_done:
            self.progress.add_xp(xp)
        # evaluate badges
        new_badges = self.progress.evaluate_badges(self.badges)
        self._refresh_all()
        for badge in new_badges:
            self._show_badge_popup(badge)

    def _show_badge_popup(self, badge: dict) -> None:
        popup = BadgePopup(
            self,
            title=f"Badge unlocked: {badge['name']}",
            subtitle=badge.get("description", ""),
            icon=badge.get("icon", "🏆"),
        )
        popup.show_at_top_right(self.width(), self.height())
