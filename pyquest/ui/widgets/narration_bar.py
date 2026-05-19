"""Narration bar: real playback controls + quick-action voice buttons.

Shows the current segment label, a play/pause/prev/next/replay/stop control
strip, and four quick-action buttons (read lesson, explain hint, encourage,
explain error). Listens to the global narrator and reflects state.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pyquest.services.tts import get_narrator


class NarrationBar(QWidget):
    # Quick-action signals (handled by lesson view to provide context)
    read_lesson = Signal()
    explain_hint = Signal()
    encourage = Signal()
    explain_error = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("NarrationBar")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        # ---- top row: status pill + transport controls ----
        top = QHBoxLayout()
        top.setSpacing(8)

        self.status_label = QLabel("🎧 Tap play to start narration")
        self.status_label.setObjectName("Pill")
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.btn_prev = self._mk_btn("⏮", "Previous segment")
        self.btn_play = self._mk_btn("▶", "Play")
        self.btn_next = self._mk_btn("⏭", "Next segment")
        self.btn_replay = self._mk_btn("↻", "Replay segment")
        self.btn_stop = self._mk_btn("⏹", "Stop narration")

        top.addWidget(self.status_label, 1)
        top.addWidget(self.btn_prev)
        top.addWidget(self.btn_play)
        top.addWidget(self.btn_next)
        top.addWidget(self.btn_replay)
        top.addWidget(self.btn_stop)
        outer.addLayout(top)

        # ---- second row: quick actions ----
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        self.btn_read = QPushButton("🔊 Read lesson")
        self.btn_hint = QPushButton("💡 Speak hint")
        self.btn_enc = QPushButton("🎉 Encourage me")
        self.btn_err = QPushButton("🩺 Explain my error")
        for b in (self.btn_read, self.btn_hint, self.btn_enc, self.btn_err):
            b.setObjectName("Ghost")
        bottom.addWidget(self.btn_read)
        bottom.addWidget(self.btn_hint)
        bottom.addWidget(self.btn_enc)
        bottom.addWidget(self.btn_err)
        bottom.addStretch(1)
        outer.addLayout(bottom)

        # ---- wire ----
        narr = get_narrator()
        narr.segment_started.connect(self._on_seg_started)
        narr.segment_finished.connect(self._on_seg_finished)
        narr.queue_finished.connect(self._on_queue_finished)
        narr.state_changed.connect(self._on_state_changed)
        narr.error_occurred.connect(self._on_narration_error)

        self.btn_play.clicked.connect(self._on_play_clicked)
        self.btn_prev.clicked.connect(narr.prev)
        self.btn_next.clicked.connect(narr.next)
        self.btn_replay.clicked.connect(narr.replay)
        self.btn_stop.clicked.connect(narr.stop)
        self.btn_read.clicked.connect(self.read_lesson)
        self.btn_hint.clicked.connect(self.explain_hint)
        self.btn_enc.clicked.connect(self.encourage)
        self.btn_err.clicked.connect(self.explain_error)

        self.set_error_enabled(False)
        self.set_hint_enabled(False)
        self._update_play_button()

    # ----------------------------------------------------------------
    def _mk_btn(self, glyph: str, tooltip: str) -> QPushButton:
        b = QPushButton(glyph)
        b.setObjectName("Ghost")
        b.setToolTip(tooltip)
        b.setFixedSize(36, 32)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def set_error_enabled(self, enabled: bool) -> None:
        self.btn_err.setEnabled(enabled)

    def set_hint_enabled(self, enabled: bool) -> None:
        self.btn_hint.setEnabled(enabled)

    # ----------------------------------------------------------------
    def _on_play_clicked(self) -> None:
        narr = get_narrator()
        if narr.state == "playing":
            narr.pause()
        elif narr.state == "paused":
            narr.resume()
        else:
            # Idle: ask the lesson view to (re)build segments and start.
            self.read_lesson.emit()

    def _on_seg_started(self, idx: int, label: str, _text: str) -> None:
        narr = get_narrator()
        total = narr.total
        tag = label or "Speaking"
        self.status_label.setText(f"🎙 {tag}  ·  {idx + 1} / {total}")

    def _on_seg_finished(self, _idx: int) -> None:
        pass

    def _on_queue_finished(self) -> None:
        self.status_label.setText("✅ Narration complete")

    def _on_state_changed(self, state: str) -> None:
        self._update_play_button(state)
        if state == "idle":
            # Reset label only if we weren't just "complete"
            current = self.status_label.text()
            if not current.startswith("✅"):
                self.status_label.setText("🎧 Tap play to start narration")

    def _on_narration_error(self, msg: str) -> None:
        self.status_label.setText(f"⚠ Voice error: {msg[:60]}")

    def _update_play_button(self, state: str | None = None) -> None:
        if state is None:
            state = get_narrator().state
        if state == "playing":
            self.btn_play.setText("⏸")
            self.btn_play.setToolTip("Pause")
        elif state == "paused":
            self.btn_play.setText("▶")
            self.btn_play.setToolTip("Resume")
        else:
            self.btn_play.setText("▶")
            self.btn_play.setToolTip("Play lesson")
