"""Mic toggle button with pulsing animation and live partial-transcript label."""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from pyquest.services.speech import get_recognizer


class MicButton(QWidget):
    """Click to arm / disarm. Shows live partial transcript while listening."""

    # Forwarded from recognizer for outside listeners.
    phrase_recognized = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.btn = QPushButton("🎤  Voice control: OFF")
        self.btn.setObjectName("Ghost")
        self.btn.setCheckable(True)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setMinimumHeight(32)
        self.btn.setToolTip("Toggle voice commands (or press Ctrl+Space)")

        self.partial_label = QLabel("")
        self.partial_label.setObjectName("Dim")
        self.partial_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout.addWidget(self.btn)
        layout.addWidget(self.partial_label, 1)

        self._opacity = QGraphicsOpacityEffect(self.btn)
        self._opacity.setOpacity(1.0)
        self.btn.setGraphicsEffect(self._opacity)
        self._pulse = QPropertyAnimation(self._opacity, b"opacity", self)
        self._pulse.setDuration(900)
        self._pulse.setStartValue(1.0)
        self._pulse.setEndValue(0.55)
        self._pulse.setEasingCurve(QEasingCurve.InOutSine)
        self._pulse.setLoopCount(-1)

        self.btn.clicked.connect(self._toggle)

        rec = get_recognizer()
        rec.listening_started.connect(self._on_listening_started)
        rec.listening_stopped.connect(self._on_listening_stopped)
        rec.partial_recognized.connect(self._on_partial)
        rec.phrase_recognized.connect(self._on_phrase)
        rec.error_occurred.connect(self._on_error)

    # ------------------------------------------------------------- API
    def is_listening(self) -> bool:
        return get_recognizer().listening

    def trigger_toggle(self) -> None:
        """Programmatic toggle (used by Space hotkey)."""
        self._toggle()

    # ------------------------------------------------------------- slots
    def _toggle(self) -> None:
        get_recognizer().toggle()

    def _on_listening_started(self) -> None:
        self.btn.setChecked(True)
        self.btn.setText("🔴  Voice control: ON  (listening...)")
        self.partial_label.setText("Say a command, e.g. 'check answer', 'next', 'show hint'")
        self._pulse.start()

    def _on_listening_stopped(self) -> None:
        self.btn.setChecked(False)
        self.btn.setText("🎤  Voice control: OFF")
        self.partial_label.setText("")
        self._pulse.stop()
        self._opacity.setOpacity(1.0)

    def _on_partial(self, text: str) -> None:
        if text:
            self.partial_label.setText(f"… {text}")

    def _on_phrase(self, text: str) -> None:
        self.partial_label.setText(f"🗣 \"{text}\"")
        self.phrase_recognized.emit(text)

    def _on_error(self, msg: str) -> None:
        self.partial_label.setText(f"⚠ {msg}")
