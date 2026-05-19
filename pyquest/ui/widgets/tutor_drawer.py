"""Slide-in AI tutor chat panel.

Lives inside the LessonView and animates from the right edge. Shows scrolling
chat history (you / tutor), a text input, a 'speak to tutor' mic toggle, and a
'speak reply' toggle. Uses the global TutorService and SpeechRecognizer.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Signal,
)
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyquest.services.speech import get_recognizer
from pyquest.services.tts import Segment, get_narrator
from pyquest.services.tutor import LessonContext, get_tutor

DRAWER_WIDTH = 460


class TutorDrawer(QFrame):
    opened = Signal()
    closed = Signal()
    about_to_send = Signal()  # emitted right before any question is sent

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("TutorDrawer")
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            "QFrame#TutorDrawer { background-color: #1A1D24; border-left: 1px solid #2A2F3A; }"
        )
        self.setFixedWidth(DRAWER_WIDTH)
        self.hide()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # ---- header ----
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("🤖  AI Tutor")
        title.setObjectName("H2")
        head.addWidget(title, 1)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setObjectName("Ghost")
        self.btn_clear.setFixedHeight(28)
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("Ghost")
        self.btn_close.setFixedSize(32, 28)
        self.btn_close.setToolTip("Close (Esc)")
        head.addWidget(self.btn_clear)
        head.addWidget(self.btn_close)
        outer.addLayout(head)

        # ---- transcript ----
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setFrameShape(QFrame.NoFrame)
        self.transcript.setStyleSheet("background: transparent;")
        self.transcript.setPlaceholderText(
            "Ask anything: 'Why is my code wrong?', 'What does an f-string do?', "
            "'Give me a hint without spoilers.'"
        )
        outer.addWidget(self.transcript, 1)

        self.thinking_label = QLabel("")
        self.thinking_label.setObjectName("Dim")
        outer.addWidget(self.thinking_label)

        # ---- voice + speak-reply toggles ----
        opts = QHBoxLayout()
        self.btn_mic = QPushButton("🎙  Speak to tutor")
        self.btn_mic.setObjectName("Ghost")
        self.btn_mic.setCheckable(True)
        self.btn_mic.setToolTip("Toggle mic to dictate your question")
        self.cb_speak = QCheckBox("Read replies aloud")
        self.cb_speak.setChecked(True)
        opts.addWidget(self.btn_mic)
        opts.addStretch(1)
        opts.addWidget(self.cb_speak)
        outer.addLayout(opts)

        # ---- input row ----
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a question and press Enter…")
        self.btn_send = QPushButton("Ask")
        self.btn_send.setObjectName("Primary")
        row.addWidget(self.input, 1)
        row.addWidget(self.btn_send)
        outer.addLayout(row)

        # ---- animation ----
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._open = False

        # ---- close shortcut ----
        self._esc = QShortcut(QKeySequence("Esc"), self)
        self._esc.activated.connect(self.close_drawer)

        # ---- streaming state ----
        self._stream_buffer = ""
        self._streaming = False
        self._mic_owned = False  # did we turn the mic on for the tutor?

        # ---- wire ----
        self.btn_close.clicked.connect(self.close_drawer)
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_send.clicked.connect(self._on_send)
        self.input.returnPressed.connect(self._on_send)
        self.btn_mic.toggled.connect(self._on_mic_toggle)

        tutor = get_tutor()
        tutor.started.connect(self._on_tutor_started)
        tutor.delta.connect(self._on_tutor_delta)
        tutor.finished.connect(self._on_tutor_finished)
        tutor.failed.connect(self._on_tutor_failed)
        tutor.speak_requested.connect(self._on_speak_request)

        rec = get_recognizer()
        rec.phrase_recognized.connect(self._on_voice_phrase)
        rec.listening_started.connect(self._on_mic_started)
        rec.listening_stopped.connect(self._on_mic_stopped)

    # ------------------------------------------------------ open / close
    def is_open(self) -> bool:
        return self._open

    def open_drawer(self) -> None:
        if self._open:
            return
        self._open = True
        parent = self.parentWidget()
        if parent is None:
            return
        # Position off-screen right, then animate in.
        h = parent.height()
        x_off = parent.width()
        x_target = parent.width() - DRAWER_WIDTH
        self.setGeometry(x_off, 0, DRAWER_WIDTH, h)
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self.pos().__class__(x_target, 0))
        self._anim.start()
        self.input.setFocus()
        self.opened.emit()

    def close_drawer(self) -> None:
        if not self._open:
            return
        self._open = False
        # If we turned the mic on, turn it off.
        if self._mic_owned and get_recognizer().listening:
            get_recognizer().stop()
        self._mic_owned = False
        if self.btn_mic.isChecked():
            self.btn_mic.blockSignals(True)
            self.btn_mic.setChecked(False)
            self.btn_mic.setText("🎙  Speak to tutor")
            self.btn_mic.blockSignals(False)
        parent = self.parentWidget()
        if parent is None:
            self.hide()
            self.closed.emit()
            return
        x_off = parent.width()
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self.pos().__class__(x_off, 0))
        self._anim.finished.connect(self._after_close)
        self._anim.start()

    def _after_close(self) -> None:
        try:
            self._anim.finished.disconnect(self._after_close)
        except (TypeError, RuntimeError):
            pass
        self.hide()
        self.closed.emit()

    def reposition(self) -> None:
        """Called when parent resizes while drawer is open."""
        parent = self.parentWidget()
        if parent is None:
            return
        h = parent.height()
        if self._open:
            x = parent.width() - DRAWER_WIDTH
        else:
            x = parent.width()
        self.setGeometry(x, 0, DRAWER_WIDTH, h)

    # ----------------------------------------------------- public API
    def update_lesson_context(self, ctx: LessonContext) -> None:
        get_tutor().set_lesson_context(ctx)

    def submit_question(
        self,
        text: str,
        *,
        speak_reply: bool | None = None,
        fresh: bool = False,
    ) -> None:
        """Programmatic ask (used by proactive triggers).

        If ``fresh`` is True, wipe the chat transcript and history first so the
        tutor doesn't contradict an answer from a previous run.
        """
        if not text.strip():
            return
        # Let listeners (LessonView) refresh lesson/code context first.
        self.about_to_send.emit()
        if fresh:
            get_tutor().cancel()
            get_tutor().reset_history()
            self.transcript.clear()
            self.thinking_label.setText("")
        self._append_role("You", text, color="#9678FF")
        wants_speak = self.cb_speak.isChecked() if speak_reply is None else speak_reply
        get_tutor().ask(text, speak_reply=wants_speak)

    # ----------------------------------------------------- handlers
    def _on_clear(self) -> None:
        self.transcript.clear()
        self.thinking_label.setText("")
        get_tutor().reset_history()

    def _on_send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.submit_question(text)

    def _on_mic_toggle(self, checked: bool) -> None:
        rec = get_recognizer()
        if checked:
            self._mic_owned = True
            rec.start()
        else:
            self._mic_owned = False
            rec.stop()

    def _on_mic_started(self) -> None:
        if self.btn_mic.isChecked():
            self.btn_mic.setText("🔴  Listening… click to stop")

    def _on_mic_stopped(self) -> None:
        if self.btn_mic.isChecked():
            self.btn_mic.blockSignals(True)
            self.btn_mic.setChecked(False)
            self.btn_mic.blockSignals(False)
        self.btn_mic.setText("🎙  Speak to tutor")

    def _on_voice_phrase(self, text: str) -> None:
        # Only accept dictated speech if the drawer is open AND the drawer's mic is the owner.
        if not self._open or not self._mic_owned:
            return
        text = text.strip()
        if not text:
            return
        # Auto-stop listening after a phrase so you don't double-send.
        get_recognizer().stop()
        self.submit_question(text)

    def _on_tutor_started(self) -> None:
        self._stream_buffer = ""
        self._streaming = True
        self.thinking_label.setText("Tutor is thinking…")
        self._append_role("Tutor", "", color="#3DDC97")

    def _on_tutor_delta(self, chunk: str) -> None:
        if not self._streaming:
            return
        self._stream_buffer += chunk
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()

    def _on_tutor_finished(self, _full: str) -> None:
        self._streaming = False
        self.thinking_label.setText("")
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n")
        self.transcript.setTextCursor(cursor)

    def _on_tutor_failed(self, msg: str) -> None:
        self._streaming = False
        self.thinking_label.setText(f"⚠ {msg}")

    def _on_speak_request(self, text: str) -> None:
        if self.cb_speak.isChecked() and text.strip():
            get_narrator().play_segments([Segment(text=text, label="Tutor")])

    # ----------------------------------------------------- helpers
    def _append_role(self, who: str, text: str, color: str) -> None:
        self.transcript.append("")  # blank line
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # who: prefix in colour
        from PySide6.QtGui import QColor, QTextCharFormat

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontWeight(700)
        cursor.insertText(f"{who}:  ", fmt)
        plain = QTextCharFormat()
        plain.setForeground(QColor("#E6E8EE"))
        cursor.insertText(text, plain)
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()
