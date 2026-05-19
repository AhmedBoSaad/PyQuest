"""First-run welcome wizard.

A 3-step modal walk-through that guides non-technical users through optional
downloads (Kokoro voice, Vosk speech model) and the AI tutor connection check.
Every step can be skipped — the app works without any of them.

Set the 'first_run_done' state flag once complete so it never shows again.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pyquest.config import APP_NAME, get_lmstudio_url
from pyquest.services import kokoro_tts, lmstudio_client
from pyquest.services.speech import get_recognizer
from pyquest.services.speech import model_available as vosk_available


# ---------------------------------------------------------------- helpers
def _eyebrow(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
        "font-size: 11px; color: #D4B361; letter-spacing: 3px;"
    )
    return lbl


def _title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "font-family: 'Instrument Serif','Cambria','Georgia',serif;"
        "font-size: 36px; color: #EEEAE0; letter-spacing: -1px; line-height: 1.05;"
    )
    lbl.setWordWrap(True)
    return lbl


def _body(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #C4BFB1; font-size: 14.5px; line-height: 1.55;")
    lbl.setWordWrap(True)
    return lbl


# ---------------------------------------------------------------- the dialog
class WelcomeWizard(QDialog):
    """Modal first-run setup. Returns when the user clicks 'Start learning'."""

    finished_setup = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setModal(True)
        self.resize(720, 540)
        self.setStyleSheet("QDialog { background-color: #1B1815; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 40, 48, 32)
        outer.setSpacing(0)

        self.progress_label = QLabel("STEP 1 OF 3")
        self.progress_label.setStyleSheet(
            "font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size: 10px; color: #928D7F; letter-spacing: 3px;"
        )
        outer.addWidget(self.progress_label)
        outer.addSpacing(12)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_voice_page())
        self.stack.addWidget(self._build_speech_page())
        self.stack.addWidget(self._build_tutor_page())
        outer.addWidget(self.stack, 1)

        # Footer with skip + next/start
        outer.addSpacing(16)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #3D3933;")
        outer.addWidget(sep)
        outer.addSpacing(14)

        foot = QHBoxLayout()
        self.btn_skip = QPushButton("Skip this step")
        self.btn_skip.setObjectName("Ghost")
        self.btn_back = QPushButton("← Back")
        self.btn_back.setObjectName("Ghost")
        self.btn_next = QPushButton("Next →")
        self.btn_next.setObjectName("Primary")
        foot.addWidget(self.btn_skip)
        foot.addStretch(1)
        foot.addWidget(self.btn_back)
        foot.addWidget(self.btn_next)
        outer.addLayout(foot)

        self.btn_skip.clicked.connect(self._advance)
        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._advance)
        self._update_footer()

    # ------------------------------------------------ pages
    def _build_voice_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        v.addWidget(_eyebrow("VOICE"))
        v.addWidget(_title("A friendly voice reads each lesson aloud."))
        v.addWidget(_body(
            "PyQuest narrates lessons using Kokoro, a neural text-to-speech model "
            "that runs entirely on your computer. No internet, no API key, no "
            "subscriptions. The model files are about 340 MB and download once."
        ))
        v.addSpacing(6)
        self.voice_status = QLabel(
            "✅ Voice model is already downloaded — you're set." if kokoro_tts.is_available()
            else "Click below to download. You can skip and do this later from Settings."
        )
        self.voice_status.setObjectName("Dim")
        self.voice_status.setWordWrap(True)
        v.addWidget(self.voice_status)

        row = QHBoxLayout()
        self.btn_dl_voice = QPushButton("⬇ Download voice (~340 MB)")
        self.btn_dl_voice.setObjectName("Primary")
        self.btn_dl_voice.setEnabled(not kokoro_tts.is_available())
        row.addWidget(self.btn_dl_voice)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)

        self.btn_dl_voice.clicked.connect(self._on_dl_voice)
        return page

    def _build_speech_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        v.addWidget(_eyebrow("VOICE COMMANDS (OPTIONAL)"))
        v.addWidget(_title("Talk to PyQuest hands-free."))
        v.addWidget(_body(
            "Toggle a mic inside any lesson and say things like 'run', 'check answer', "
            "'show hint', 'next', or 'ask tutor'. Speech recognition is offline "
            "(Vosk, ~50 MB). Totally optional — skip if you'd rather click."
        ))
        v.addSpacing(6)
        self.speech_status = QLabel(
            "✅ Speech model is already downloaded." if vosk_available()
            else "Click below to download. You can skip and do this later."
        )
        self.speech_status.setObjectName("Dim")
        self.speech_status.setWordWrap(True)
        v.addWidget(self.speech_status)

        row = QHBoxLayout()
        self.btn_dl_speech = QPushButton("⬇ Download speech model (~50 MB)")
        self.btn_dl_speech.setObjectName("Primary")
        self.btn_dl_speech.setEnabled(not vosk_available())
        row.addWidget(self.btn_dl_speech)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)

        self.btn_dl_speech.clicked.connect(self._on_dl_speech)
        return page

    def _build_tutor_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        v.addWidget(_eyebrow("AI TUTOR (OPTIONAL)"))
        v.addWidget(_title("A patient tutor that knows your code."))
        v.addWidget(_body(
            "PyQuest can chat with a local LLM running in LM Studio. The tutor sees "
            "your current lesson, your code, and your last error — and can hint, "
            "explain, or (in drill-sergeant mode) roast you. Fully local. No cost.\n\n"
            "Install LM Studio from lmstudio.ai, load any chat model, then click "
            "'Start Server' in the Local Server tab."
        ))
        v.addSpacing(6)
        self.tutor_status = QLabel("Click below to test the connection.")
        self.tutor_status.setObjectName("Dim")
        self.tutor_status.setWordWrap(True)
        v.addWidget(self.tutor_status)

        row = QHBoxLayout()
        self.btn_test_tutor = QPushButton("🔌 Test LM Studio connection")
        self.btn_test_tutor.setObjectName("Primary")
        row.addWidget(self.btn_test_tutor)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)

        self.btn_test_tutor.clicked.connect(self._on_test_tutor)
        return page

    # ------------------------------------------------ download handlers
    def _on_dl_voice(self) -> None:
        self.btn_dl_voice.setEnabled(False)
        self.voice_status.setText("⏬ Downloading voice model… 0%")

        def progress(name: str, pct: int) -> None:
            QTimer.singleShot(
                0,
                lambda p=pct, n=name: self.voice_status.setText(f"⏬ Downloading {n}… {p}%"),
            )

        def done(exc) -> None:
            if exc is None:
                QTimer.singleShot(0, lambda: self.voice_status.setText("✅ Voice ready."))
            else:
                QTimer.singleShot(
                    0,
                    lambda: (
                        self.voice_status.setText(f"⚠ Download failed: {exc}"),
                        self.btn_dl_voice.setEnabled(True),
                    ),
                )

        kokoro_tts.download_async(progress, done)

    def _on_dl_speech(self) -> None:
        self.btn_dl_speech.setEnabled(False)
        self.speech_status.setText("⏬ Downloading speech model… 0%")
        rec = get_recognizer()

        def on_progress(pct: int) -> None:
            self.speech_status.setText(f"⏬ Downloading speech model… {pct}%")

        def on_ready() -> None:
            self.speech_status.setText("✅ Speech model ready.")

        def on_error(msg: str) -> None:
            self.speech_status.setText(f"⚠ {msg}")
            self.btn_dl_speech.setEnabled(True)

        # Connect once (Qt allows duplicates but we don't need that).
        try:
            rec.model_download_progress.disconnect()
            rec.model_ready.disconnect()
            rec.error_occurred.disconnect()
        except (TypeError, RuntimeError):
            pass
        rec.model_download_progress.connect(on_progress)
        rec.model_ready.connect(on_ready)
        rec.error_occurred.connect(on_error)
        rec.ensure_model_async()

    def _on_test_tutor(self) -> None:
        self.btn_test_tutor.setEnabled(False)
        self.tutor_status.setText("Connecting…")

        def _job() -> None:
            url = get_lmstudio_url()
            try:
                models = lmstudio_client.list_models(url, timeout=2.0)
            except Exception as exc:  # noqa: BLE001
                QTimer.singleShot(
                    0,
                    lambda e=exc: (
                        self.tutor_status.setText(
                            f"⚠ Couldn't reach LM Studio at {url}.\n"
                            "Open LM Studio → Local Server → Start Server.\n"
                            "You can do this later from Settings."
                        ),
                        self.btn_test_tutor.setEnabled(True),
                    ),
                )
                return
            if not models:
                QTimer.singleShot(
                    0,
                    lambda: (
                        self.tutor_status.setText(
                            "✅ Reached LM Studio, but no model is loaded. "
                            "Load a chat model and click again."
                        ),
                        self.btn_test_tutor.setEnabled(True),
                    ),
                )
                return
            QTimer.singleShot(
                0,
                lambda: (
                    self.tutor_status.setText(
                        f"✅ Connected. Found {len(models)} model(s): {', '.join(models[:3])}"
                    ),
                ),
            )

        threading.Thread(target=_job, daemon=True).start()

    # ------------------------------------------------ navigation
    def _advance(self) -> None:
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
            self._update_footer()
        else:
            self.finished_setup.emit()
            self.accept()

    def _go_back(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_footer()

    def _update_footer(self) -> None:
        total = self.stack.count()
        idx = self.stack.currentIndex()
        self.progress_label.setText(f"STEP {idx + 1} OF {total}")
        self.btn_back.setEnabled(idx > 0)
        if idx == total - 1:
            self.btn_next.setText("Start learning  →")
            self.btn_skip.setText("Finish")
        else:
            self.btn_next.setText("Next  →")
            self.btn_skip.setText("Skip this step")
