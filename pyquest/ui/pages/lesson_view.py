"""Lesson view: explanation + editor + console + hints + auto-check + voice."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyquest.config import get_autoplay, get_proactive_tutor
from pyquest.core.checker import check_exercise
from pyquest.core.lesson_loader import Lesson
from pyquest.core.runner import run_user_code
from pyquest.services.commands import parse_command
from pyquest.services.tts import (
    Segment,
    build_lesson_segments,
    encouragement_segment,
    error_segment,
    get_narrator,
    hint_segment,
)
from pyquest.services.tutor import LessonContext
from pyquest.ui.pages.quiz_view import QuizView
from pyquest.ui.widgets.code_editor import CodeEditor
from pyquest.ui.widgets.console import ConsoleView
from pyquest.ui.widgets.mic_button import MicButton
from pyquest.ui.widgets.narration_bar import NarrationBar
from pyquest.ui.widgets.tutor_drawer import TutorDrawer


class LessonView(QWidget):
    lesson_completed = Signal(str, int, int, int)  # lesson_id, xp, quiz_score, quiz_total
    back_to_path = Signal()
    next_lesson_requested = Signal()  # user wants to advance to the next lesson

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._lesson: Lesson | None = None
        self._hint_index = 0
        self._last_stderr = ""
        self._last_run_passed = False
        # When the tutor asks a yes/no question (e.g. "ready for the quiz?"),
        # this holds the action to run on 'yes'. Cleared on 'no' or any other command.
        self._pending_yes_action: callable | None = None
        self._pending_yes_label: str = ""

        self._outer_layout = QVBoxLayout(self)
        outer = self._outer_layout
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)
        # Cache the default right margin so we can restore it when the drawer closes.
        self._default_right_margin = 20

        # Top bar with back button + title
        top = QHBoxLayout()
        top.setSpacing(20)
        self.btn_back = QPushButton("← BACK")
        self.btn_back.setObjectName("Ghost")
        self.btn_back.setStyleSheet(
            "QPushButton#Ghost { font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size: 11px; letter-spacing: 2px; color: #928D7F; padding: 6px 12px; }"
        )
        self.btn_back.clicked.connect(self._on_back)

        # Title block (eyebrow + serif headline)
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        self.eyebrow_label = QLabel("CHAPTER 01")
        self.eyebrow_label.setObjectName("Eyebrow")
        self.title_label = QLabel("")
        self.title_label.setStyleSheet(
            "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            "font-size: 30px; color: #EEEAE0; letter-spacing: -1px; line-height: 1.1;"
        )
        title_block.addWidget(self.eyebrow_label)
        title_block.addWidget(self.title_label)

        self.btn_ask_tutor = QPushButton("Ask tutor")
        self.btn_ask_tutor.setObjectName("Primary")
        self.btn_ask_tutor.setToolTip("Open the AI tutor drawer (or say 'ask tutor')")
        self.xp_pill = QLabel("+0 XP")
        self.xp_pill.setObjectName("PillAccent")
        top.addWidget(self.btn_back)
        top.addLayout(title_block, 1)
        top.addWidget(self.btn_ask_tutor)
        top.addWidget(self.xp_pill)
        outer.addLayout(top)

        # Voice control toggle row
        self.mic = MicButton()
        self.mic.phrase_recognized.connect(self._on_voice_command)
        outer.addWidget(self.mic)

        # Ctrl+Space anywhere in the lesson view toggles the mic.
        self._mic_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        self._mic_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._mic_shortcut.activated.connect(self.mic.trigger_toggle)

        self.objective_label = QLabel("")
        self.objective_label.setObjectName("Dim")
        self.objective_label.setWordWrap(True)
        outer.addWidget(self.objective_label)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        # Page 0: lesson content
        self._lesson_page = self._build_lesson_page()
        self.stack.addWidget(self._lesson_page)

        # Page 1: quiz
        self.quiz = QuizView()
        self.quiz.quiz_finished.connect(self._on_quiz_finished)
        self.stack.addWidget(self.quiz)

        # Page 2: completion
        self._done_page = self._build_done_page()
        self.stack.addWidget(self._done_page)

        # AI tutor drawer (overlay, parented to self so it floats over content)
        self.tutor_drawer = TutorDrawer(self)
        self.tutor_drawer.about_to_send.connect(self._refresh_tutor_context)
        self.tutor_drawer.opened.connect(self._on_drawer_opened)
        self.tutor_drawer.closed.connect(self._on_drawer_closed)
        self.btn_ask_tutor.clicked.connect(self._toggle_tutor_drawer)

    # ------------------------------------------------------------------ build
    def _build_lesson_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        self.voice_bar = NarrationBar()
        self.voice_bar.read_lesson.connect(self._voice_read_lesson)
        self.voice_bar.explain_hint.connect(self._voice_explain_hint)
        self.voice_bar.encourage.connect(self._voice_encourage)
        self.voice_bar.explain_error.connect(self._voice_explain_error)
        self.voice_bar.set_error_enabled(False)
        v.addWidget(self.voice_bar)

        # Listen for narration progress so we can highlight the current segment.
        narr = get_narrator()
        narr.segment_started.connect(self._on_seg_started)

        splitter = QSplitter(Qt.Horizontal)

        # ---- Left: explanation + exercise prompt + hints ----
        left = QFrame()
        left.setObjectName("Card")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(18, 16, 18, 16)
        ll.setSpacing(10)

        self.explanation = QTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setFrameShape(QFrame.NoFrame)
        self.explanation.setStyleSheet("background: transparent;")
        ll.addWidget(self.explanation, 1)

        self.exercise_box = QFrame()
        self.exercise_box.setObjectName("CardAccent")
        ex_l = QVBoxLayout(self.exercise_box)
        ex_l.setContentsMargins(14, 12, 14, 12)
        ex_h = QLabel("Your task")
        ex_h.setObjectName("H3")
        self.exercise_label = QLabel("")
        self.exercise_label.setWordWrap(True)
        self.exercise_label.setStyleSheet("font-size: 14px;")
        self.expected_label = QLabel("")
        self.expected_label.setObjectName("Dim")
        self.expected_label.setWordWrap(True)
        ex_l.addWidget(ex_h)
        ex_l.addWidget(self.exercise_label)
        ex_l.addWidget(self.expected_label)
        ll.addWidget(self.exercise_box)

        # Hints
        hint_row = QHBoxLayout()
        self.btn_hint = QPushButton("💡 Show hint")
        self.btn_hint.setObjectName("Ghost")
        self.btn_hint.clicked.connect(self._show_next_hint)
        hint_row.addWidget(self.btn_hint)
        hint_row.addStretch(1)
        ll.addLayout(hint_row)

        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #FFB454;")
        ll.addWidget(self.hint_label)

        # ---- Right: editor + run + console ----
        right = QFrame()
        right.setObjectName("Card")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(14, 14, 14, 14)
        rl.setSpacing(8)

        editor_header = QHBoxLayout()
        eh = QLabel("Your code")
        eh.setObjectName("H3")
        editor_header.addWidget(eh)
        editor_header.addStretch(1)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setObjectName("Ghost")
        self.btn_reset.clicked.connect(self._reset_code)
        editor_header.addWidget(self.btn_reset)
        rl.addLayout(editor_header)

        self.editor = CodeEditor()
        rl.addWidget(self.editor, 1)
        # Debounced tutor-context refresh on every code edit so the AI always
        # sees the user's latest code without polling.
        self._ctx_timer = QTimer(self)
        self._ctx_timer.setSingleShot(True)
        self._ctx_timer.setInterval(400)
        self._ctx_timer.timeout.connect(self._maybe_refresh_tutor_context)
        self.editor.textChanged.connect(self._ctx_timer.start)

        # input panel (visible only for input-using lessons)
        self.input_box = QFrame()
        ib_l = QVBoxLayout(self.input_box)
        ib_l.setContentsMargins(0, 0, 0, 0)
        ib_l.setSpacing(4)
        ib_lab = QLabel("Inputs (one per line, sent to input() calls):")
        ib_lab.setObjectName("Dim")
        self.input_edit = QPlainTextEdit()
        self.input_edit.setMaximumHeight(70)
        ib_l.addWidget(ib_lab)
        ib_l.addWidget(self.input_edit)
        rl.addWidget(self.input_box)
        self.input_box.setVisible(False)

        run_row = QHBoxLayout()
        self.btn_run = QPushButton("▶  Run")
        self.btn_run.setObjectName("Primary")
        self.btn_run.clicked.connect(self._on_run)
        self.btn_check = QPushButton("✓  Check answer")
        self.btn_check.setObjectName("Success")
        self.btn_check.clicked.connect(self._on_check)
        self.btn_quiz = QPushButton("Continue to quiz ▶")
        self.btn_quiz.setObjectName("Primary")
        self.btn_quiz.setEnabled(False)
        self.btn_quiz.clicked.connect(self._on_continue_to_quiz)
        run_row.addWidget(self.btn_run)
        run_row.addWidget(self.btn_check)
        run_row.addStretch(1)
        run_row.addWidget(self.btn_quiz)
        rl.addLayout(run_row)

        self.console = ConsoleView()
        self.console.setMinimumHeight(140)
        rl.addWidget(self.console)

        self.feedback_label = QLabel("")
        self.feedback_label.setWordWrap(True)
        rl.addWidget(self.feedback_label)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([520, 580])
        v.addWidget(splitter, 1)
        return page

    def _build_done_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(80, 60, 80, 60)
        v.setSpacing(0)
        v.setAlignment(Qt.AlignCenter)

        # Eyebrow
        eyebrow = QLabel("CHAPTER COMPLETE")
        eyebrow.setStyleSheet(
            "font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size: 11px; color: #D4B361; letter-spacing: 4px;"
        )
        eyebrow.setAlignment(Qt.AlignCenter)
        v.addWidget(eyebrow)
        v.addSpacing(18)

        # Huge serif headline: 'Well done.'
        self.done_title = QLabel("Well done.")
        self.done_title.setStyleSheet(
            "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
            "font-size: 72px; color: #EEEAE0; letter-spacing: -3px; line-height: 0.98;"
        )
        self.done_title.setAlignment(Qt.AlignCenter)
        v.addWidget(self.done_title)
        v.addSpacing(18)

        self.done_sub = QLabel("")
        self.done_sub.setStyleSheet("color: #C4BFB1; font-size: 16px; line-height: 1.55;")
        self.done_sub.setAlignment(Qt.AlignCenter)
        self.done_sub.setWordWrap(True)
        v.addWidget(self.done_sub)
        v.addSpacing(28)

        # Roman-numeral year scribed line ("MMXXVI")
        scribe = QLabel("· MMXXVI ·")
        scribe.setStyleSheet(
            "font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size: 11px; color: #928D7F; letter-spacing: 6px;"
        )
        scribe.setAlignment(Qt.AlignCenter)
        v.addWidget(scribe)
        v.addSpacing(28)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        row.setSpacing(10)
        self.done_back = QPushButton("Back to path")
        self.done_back.setObjectName("Ghost")
        self.done_back.clicked.connect(self.back_to_path.emit)
        self.done_next = QPushButton("Next chapter  →")
        self.done_next.setObjectName("Primary")
        self.done_next.clicked.connect(self.next_lesson_requested.emit)
        row.addWidget(self.done_back)
        row.addWidget(self.done_next)
        v.addLayout(row)
        return page

    # ------------------------------------------------------------------ navigation
    def _clear_pending_yes(self) -> None:
        """Drop any dangling yes/no callback so it can't fire after a navigation."""
        self._pending_yes_action = None
        self._pending_yes_label = ""

    def _on_back(self) -> None:
        self._clear_pending_yes()
        get_narrator().stop()
        self.back_to_path.emit()

    # ------------------------------------------------------------------ tutor drawer
    def _toggle_tutor_drawer(self) -> None:
        if self.tutor_drawer.is_open():
            self.tutor_drawer.close_drawer()
        else:
            self._refresh_tutor_context()
            self.tutor_drawer.open_drawer()

    def _on_drawer_opened(self) -> None:
        # Reserve room on the right so the drawer doesn't overlap the lesson content.
        from pyquest.ui.widgets.tutor_drawer import DRAWER_WIDTH
        m = self._outer_layout.contentsMargins()
        self._outer_layout.setContentsMargins(m.left(), m.top(), DRAWER_WIDTH + 12, m.bottom())

    def _on_drawer_closed(self) -> None:
        m = self._outer_layout.contentsMargins()
        self._outer_layout.setContentsMargins(m.left(), m.top(), self._default_right_margin, m.bottom())

    def _maybe_refresh_tutor_context(self) -> None:
        """Debounced refresh: only do work when the drawer is actually open.

        Stops the editor's textChanged from rebuilding the LessonContext on every
        keystroke while the AI tutor isn't visible.
        """
        if not self.tutor_drawer.is_open():
            return
        self._refresh_tutor_context()

    def _refresh_tutor_context(self) -> None:
        if not self._lesson:
            return
        idx = self.stack.currentIndex()
        page = "lesson" if idx == 0 else ("quiz" if idx == 1 else "done")
        ctx = LessonContext(
            title=self._lesson.title,
            order=self._lesson.order,
            objective=self._lesson.objective,
            explanation_md=self._lesson.explanation_md,
            exercise_prompt=self._lesson.exercise_prompt,
            expected_output=self._lesson.expected_output,
            starter_code=self._lesson.starter_code,
            user_code=self.editor.toPlainText(),
            last_stdout=self.console.toPlainText(),
            last_stderr=self._last_stderr,
            page=page,
        )
        if page == "quiz" and self._lesson.quiz:
            qi = self.quiz._index if 0 <= self.quiz._index < len(self._lesson.quiz) else 0
            q = self._lesson.quiz[qi]
            ctx.quiz_question = q.get("q", "")
            ctx.quiz_options = list(q.get("options", []))
            ctx.quiz_progress = f"Question {qi + 1} of {len(self._lesson.quiz)}"
        self.tutor_drawer.update_lesson_context(ctx)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "tutor_drawer"):
            self.tutor_drawer.reposition()

    # ------------------------------------------------------------------ load
    def load_lesson(self, lesson: Lesson) -> None:
        # Stop any prior narration before switching lessons.
        get_narrator().stop()
        # Close the AI tutor drawer and wipe its conversation so the new lesson
        # starts with a fresh tutor context.
        if hasattr(self, "tutor_drawer") and self.tutor_drawer.is_open():
            self.tutor_drawer.close_drawer()
        from pyquest.services.tutor import get_tutor
        get_tutor().reset_history()
        get_tutor().reset_mistakes()  # rage resets between lessons
        get_tutor().cancel()
        self._lesson = lesson
        self._hint_index = 0
        self._last_stderr = ""
        self._last_run_passed = False
        self._pending_yes_action = None
        self._pending_yes_label = ""
        self.eyebrow_label.setText(f"CHAPTER {lesson.order:02d}")
        self.title_label.setText(lesson.title)
        self.objective_label.setText(lesson.objective)
        self.xp_pill.setText(f"+{lesson.xp_reward} XP")

        self.explanation.setMarkdown(lesson.explanation_md or "")
        self.exercise_label.setText(lesson.exercise_prompt or "(No exercise; read the lesson and continue.)")
        if lesson.expected_output:
            self.expected_label.setText(f"Expected output: {lesson.expected_output}")
        else:
            self.expected_label.setText("")
        self.editor.setPlainText(lesson.starter_code or "")
        self.console.reset()
        self.feedback_label.setText("")
        self.hint_label.setText("")
        self.btn_hint.setText(f"💡 Show hint (1/{max(1, len(lesson.hints))})")
        self.btn_hint.setEnabled(bool(lesson.hints))
        self.voice_bar.set_hint_enabled(False)
        self.voice_bar.set_error_enabled(False)
        self.btn_quiz.setEnabled(False)

        # Show input panel if exercise uses input()
        uses_input = "input(" in (lesson.starter_code or "") or "input(" in (lesson.example_code or "")
        if check_marker := lesson.check.get("inputs"):
            self.input_edit.setPlainText("\n".join(check_marker))
            uses_input = True
        else:
            self.input_edit.setPlainText("")
        self.input_box.setVisible(uses_input)

        # Concept-only lessons (no exercise) -> jump-to-quiz button enabled
        if lesson.check.get("type") == "none":
            self.btn_run.setEnabled(False)
            self.btn_check.setEnabled(False)
            self.btn_quiz.setEnabled(True)
            self.btn_quiz.setText("Continue ▶" if not lesson.quiz else "Continue to quiz ▶")
            self.feedback_label.setText("This is a reading lesson. When you're ready, continue.")
        else:
            self.btn_run.setEnabled(True)
            self.btn_check.setEnabled(True)

        self.stack.setCurrentIndex(0)

        # Auto-narrate the lesson if autoplay is enabled.
        if get_autoplay():
            self._voice_read_lesson()

    # ------------------------------------------------------------------ actions
    def _reset_code(self) -> None:
        if self._lesson is not None:
            self.editor.setPlainText(self._lesson.starter_code or "")
            self.console.reset()
            self.feedback_label.setText("")

    def _show_next_hint(self) -> None:
        if not self._lesson or not self._lesson.hints:
            return
        idx = min(self._hint_index, len(self._lesson.hints) - 1)
        hint_text = self._lesson.hints[idx]
        self.hint_label.setText(f"Hint {idx + 1}: {hint_text}")
        self.voice_bar.set_hint_enabled(True)
        self._hint_index = min(self._hint_index + 1, len(self._lesson.hints))
        remaining = len(self._lesson.hints) - self._hint_index
        if remaining > 0:
            self.btn_hint.setText(f"💡 Next hint ({self._hint_index + 1}/{len(self._lesson.hints)})")
        else:
            self.btn_hint.setText("💡 No more hints")
            self.btn_hint.setEnabled(False)
        # Auto-speak the hint
        if get_autoplay():
            seg = hint_segment(idx + 1, len(self._lesson.hints), hint_text)
            get_narrator().play_segments([seg])

    def _on_run(self):
        code = self.editor.toPlainText()
        stdin_text = self.input_edit.toPlainText() if self.input_box.isVisible() else ""
        if stdin_text and not stdin_text.endswith("\n"):
            stdin_text += "\n"
        self.console.reset()
        self.feedback_label.setText("Running…")
        result = run_user_code(code, stdin_text=stdin_text)
        if result.stdout:
            self.console.append_text(result.stdout)
        if result.stderr:
            self.console.append_text(result.stderr, color="#FF6B6B")
        if not result.stdout and not result.stderr:
            self.console.append_text("(no output)\n", color="#8A92A6")
        self._last_stderr = result.stderr
        has_err = bool(result.stderr.strip())
        self.voice_bar.set_error_enabled(has_err)
        if result.success:
            self.feedback_label.setText("Code ran without errors. Click 'Check answer' to verify.")
            self.feedback_label.setStyleSheet("color: #3DDC97;")
        elif result.timed_out:
            self.feedback_label.setText("Your code timed out. You may have an infinite loop.")
            self.feedback_label.setStyleSheet("color: #FFB454;")
        elif result.blocked:
            self.feedback_label.setText("Blocked by sandbox: " + result.block_reason)
            self.feedback_label.setStyleSheet("color: #FFB454;")
        else:
            self.feedback_label.setText("Code finished with an error. Read the message in red.")
            self.feedback_label.setStyleSheet("color: #FF6B6B;")
        # Proactive AI tutor on Python error. If disabled, fall back to the static narrator.
        if has_err:
            if get_proactive_tutor():
                from pyquest.services.tutor import get_tutor
                get_tutor().bump_mistakes()
                self._refresh_tutor_context()
                self.tutor_drawer.open_drawer()
                self.tutor_drawer.submit_question(
                    "My code just raised the error shown in the context. "
                    "Explain what it means in plain English and how to fix it without writing the full solution.",
                    fresh=True,
                )
            elif get_autoplay():
                get_narrator().play_segments([error_segment(result.stderr)])
        return result

    def _on_check(self) -> None:
        if not self._lesson:
            return
        result = self._on_run()
        if result is None:
            return
        check = self._lesson.check
        outcome = check_exercise(check, self.editor.toPlainText(), result.stdout, result.stderr)
        if outcome.passed:
            self._last_run_passed = True
            self.feedback_label.setText(f"✅ {outcome.feedback}")
            self.feedback_label.setStyleSheet("color: #3DDC97; font-weight: 600;")
            self.btn_quiz.setEnabled(True)
            self._speak_correct_and_offer_next()
        else:
            self._last_run_passed = False
            self.feedback_label.setText(f"❌ {outcome.feedback}")
            self.feedback_label.setStyleSheet("color: #FFB454;")
            self._speak_correction(result.stdout, result.stderr, outcome.feedback)

    # ----------------------------------------------- spoken feedback / yes-no
    def _speak_correct_and_offer_next(self) -> None:
        """After a correct answer, congratulate and ask if we should continue."""
        if not self._lesson:
            return
        text = (
            f"That's correct! Nicely done. You earned {self._lesson.xp_reward} experience "
            f"points. Would you like to continue to the quiz?"
            if self._lesson.quiz
            else
            f"That's correct! You earned {self._lesson.xp_reward} experience points. "
            f"Ready to move on?"
        )
        get_narrator().play_segments([Segment(text=text, label="Result")])
        self._pending_yes_action = self._on_continue_to_quiz
        self._pending_yes_label = "continue to the quiz" if self._lesson.quiz else "move on"

    def _speak_correction(self, stdout: str, stderr: str, feedback: str) -> None:
        """After a wrong answer, ask the AI tutor to give a personalised explanation."""
        if not self._lesson:
            return

        # If proactive tutoring is enabled, fire the LLM for a tailored answer.
        if get_proactive_tutor():
            from pyquest.services.tutor import get_tutor
            err = (stderr or "").strip()
            # Don't double-count: _on_run() already bumped if stderr was present.
            if not err:
                get_tutor().bump_mistakes()
            expected = (self._lesson.expected_output or "").strip()
            got = (stdout or "").strip()

            self._refresh_tutor_context()
            if err:
                question = (
                    "My code didn't pass and produced this error. Explain in plain English "
                    "what's wrong and give me ONE concrete hint without writing the full solution."
                )
            elif expected and got and expected != got:
                if expected.lower() == got.lower():
                    question = (
                        f"My output is '{got}' but the expected output is '{expected}'. "
                        "Tell me what's different and a hint to fix it without giving the answer."
                    )
                else:
                    question = (
                        f"My output is '{got}' but the expected output is '{expected}'. "
                        "Explain what's different and give one short hint."
                    )
            else:
                question = (
                    f"The auto-checker said: {feedback}. "
                    "Help me understand what to fix without giving me the full solution."
                )

            self.tutor_drawer.open_drawer()
            self.tutor_drawer.submit_question(question, fresh=True)
            self._pending_yes_action = None
            self._pending_yes_label = ""
            return

        # ---- fallback: static spoken correction (LLM disabled) ----
        expected = (self._lesson.expected_output or "").strip()
        got = (stdout or "").strip()
        if stderr.strip():
            tail = stderr.strip().splitlines()[-1]
            text = (
                f"Not quite. Your code raised an error. The message was: {tail}. "
                "Read your code line by line. Want me to give you a hint?"
            )
        elif expected and got and expected != got:
            if expected.lower() == got.lower():
                text = (
                    f"You're really close! The output should be exactly '{expected}', "
                    f"but yours was '{got}'. Check the capital letters. Want a hint?"
                )
            else:
                text = (
                    f"Almost! Expected '{expected}', got '{got}'. "
                    "Compare them character by character. Want a hint?"
                )
        else:
            text = f"Not quite. {feedback}. Want me to give you a hint?"
        get_narrator().play_segments([Segment(text=text, label="Correction")])
        self._pending_yes_action = self._show_next_hint
        self._pending_yes_label = "show a hint"

    # ----------------------------------------------- voice command dispatcher
    def _on_voice_command(self, utterance: str) -> None:
        """Recognized phrase from the mic. Route to an action."""
        cmd = parse_command(utterance)
        if cmd is None:
            return
        tag, params = cmd

        # If we asked a yes/no question, intercept yes/no first.
        if self._pending_yes_action is not None:
            if tag == "yes":
                action = self._pending_yes_action
                self._pending_yes_action = None
                self._pending_yes_label = ""
                action()
                return
            if tag == "no":
                self._pending_yes_action = None
                self._pending_yes_label = ""
                get_narrator().play_segments(
                    [Segment(text="Okay, take your time. Let me know when you're ready.", label="Acknowledged")]
                )
                return

        # Quiz options route to the quiz when it's visible.
        if tag == "quiz_pick" and self.stack.currentIndex() == 1:
            idx = int(params.get("index", 0))
            self.quiz.pick_option_by_index(idx)
            return

        # Lesson-page commands.
        on_lesson_page = self.stack.currentIndex() == 0
        if tag == "run" and on_lesson_page and self.btn_run.isEnabled():
            self._on_run()
        elif tag == "check" and on_lesson_page and self.btn_check.isEnabled():
            self._on_check()
        elif tag == "hint" and on_lesson_page and self.btn_hint.isEnabled():
            self._show_next_hint()
        elif tag == "next":
            if on_lesson_page and self.btn_quiz.isEnabled():
                self._on_continue_to_quiz()
            elif self.stack.currentIndex() == 2:
                self.next_lesson_requested.emit()
            elif self.stack.currentIndex() == 1:
                # In the middle of the quiz, "next" advances if a question is answered.
                self.quiz.advance_if_ready()
        elif tag == "back":
            self._on_back()
        elif tag == "retry":
            self._reset_code()
        elif tag == "repeat":
            get_narrator().replay()
        elif tag == "skip":
            get_narrator().next()
        elif tag == "stop":
            get_narrator().stop()
        elif tag == "pause":
            get_narrator().pause()
        elif tag == "resume":
            get_narrator().resume()
        elif tag == "read":
            self._voice_read_lesson()
        elif tag == "encourage":
            self._voice_encourage()
        elif tag == "explain_error":
            self._voice_explain_error()
        elif tag == "ask_tutor":
            self._refresh_tutor_context()
            self.tutor_drawer.open_drawer()
        elif tag == "close_tutor":
            self.tutor_drawer.close_drawer()

    def _on_continue_to_quiz(self) -> None:
        if not self._lesson:
            return
        self._clear_pending_yes()
        # Close the tutor drawer when transitioning to the quiz so it doesn't
        # keep talking about old code.
        if self.tutor_drawer.is_open():
            self.tutor_drawer.close_drawer()
        from pyquest.services.tutor import get_tutor
        get_tutor().cancel()
        if self._lesson.quiz:
            self.quiz.start(self._lesson.quiz)
            self.stack.setCurrentIndex(1)
            self._refresh_tutor_context()  # quiz context now active
        else:
            self._on_quiz_finished(0, 0)

    def _on_quiz_finished(self, score: int, total: int) -> None:
        if not self._lesson:
            return
        self._clear_pending_yes()
        # Close drawer + cancel any in-flight tutor reply so the lesson-complete
        # screen isn't fighting with stale AI output.
        if self.tutor_drawer.is_open():
            self.tutor_drawer.close_drawer()
        from pyquest.services.tutor import get_tutor
        get_tutor().cancel()

        bonus = score * 10 if total else 0
        total_xp = self._lesson.xp_reward + bonus
        sub = f"+{self._lesson.xp_reward} XP for the lesson"
        if total:
            sub += f"\nQuiz: {score} / {total}  (+{bonus} XP bonus)"
        self.done_sub.setText(sub)
        self.stack.setCurrentIndex(2)
        self.lesson_completed.emit(self._lesson.id, total_xp, score, total)
        self._refresh_tutor_context()  # page is now "done"

        # Voice prompt: ask if ready for next lesson, then a "yes" advances.
        get_narrator().play_segments(
            [
                Segment(
                    text=(
                        f"Lesson complete. You earned {total_xp} experience points. "
                        f"Ready for the next lesson? Say 'yes' or 'next' to continue."
                    ),
                    label="Lesson complete",
                )
            ]
        )
        self._pending_yes_action = self.next_lesson_requested.emit
        self._pending_yes_label = "go to the next lesson"

    # ------------------------------------------------------------------ voice
    def _voice_read_lesson(self) -> None:
        if not self._lesson:
            return
        segments = build_lesson_segments(self._lesson)
        get_narrator().play_segments(segments)

    def _voice_explain_hint(self) -> None:
        if not self._lesson or not self.hint_label.text():
            return
        # current hint = the most recently revealed one
        idx = max(1, self._hint_index)
        total = max(1, len(self._lesson.hints))
        # hint_label currently shows "Hint N: text"; reuse the raw text
        seg = hint_segment(idx, total, self._lesson.hints[idx - 1] if idx <= len(self._lesson.hints) else self.hint_label.text())
        get_narrator().play_segments([seg])

    def _voice_encourage(self) -> None:
        get_narrator().play_segments([encouragement_segment()])

    def _voice_explain_error(self) -> None:
        if self._last_stderr.strip():
            get_narrator().play_segments([error_segment(self._last_stderr)])

    # ------------------------------------------------------------------ narration UI sync
    def _on_seg_started(self, _idx: int, label: str, _text: str) -> None:
        # Light, non-intrusive feedback in the feedback label.
        if self._lesson is None:
            return
        if label and label not in ("Encouragement", "Error help"):
            current = self.feedback_label.text()
            # Only set if we aren't showing a check result.
            if not current.startswith(("✅", "❌")):
                self.feedback_label.setText(f"🎙 Narrating: {label}")
                self.feedback_label.setStyleSheet("color: #8A92A6;")
