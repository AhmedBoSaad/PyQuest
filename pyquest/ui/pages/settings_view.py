"""Settings page: Kokoro voice + Vosk speech model + LM Studio."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pyquest.config import (
    APP_NAME,
    APP_VERSION,
    get_autoplay,
    get_kokoro_voice,
    get_lmstudio_model,
    get_lmstudio_url,
    get_proactive_tutor,
    get_theme,
    get_tutor_persona,
    save_env,
)
from pyquest.services import kokoro_tts, lmstudio_client
from pyquest.services.speech import get_recognizer, model_available
from pyquest.services.tts import get_narrator


class _KokoroBridge(QObject):
    """Marshals Kokoro download/playback events from worker threads to the UI thread."""
    progress = Signal(str, int)  # filename, percent
    done = Signal(str)           # "" on success, error text otherwise
    play_ready = Signal(object, int)  # samples, sr
    test_error = Signal(str)


class SettingsPage(QWidget):
    saved = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # Page wrapper: title + scroll area so cards never overlap when the
        # window shrinks. The scroll area holds the actual content layout.
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(28, 28, 28, 16)
        page_layout.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("H1")
        page_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page_layout.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 12, 0)  # right pad for scrollbar gutter
        outer.setSpacing(16)

        # ----- Appearance card -----
        ap = QFrame()
        ap.setObjectName("Card")
        apl = QVBoxLayout(ap)
        apl.setContentsMargins(20, 16, 20, 16)
        apl.setSpacing(10)
        aph = QLabel("Appearance")
        aph.setObjectName("H2")
        apsub = QLabel(
            "Switch between dark (warm ink) and light (warm cream) themes. "
            "Same editorial layout, same gold accent."
        )
        apsub.setObjectName("Dim")
        apsub.setWordWrap(True)
        apl.addWidget(aph)
        apl.addWidget(apsub)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark (warm ink)", "dark")
        self.theme_combo.addItem("Light (warm cream)", "light")
        current_theme = get_theme()
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break
        apl.addWidget(self._row("Theme", self.theme_combo))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_change)
        outer.addWidget(ap)

        # ----- Kokoro offline voice card -----
        kk = QFrame()
        kk.setObjectName("Card")
        kkl = QVBoxLayout(kk)
        kkl.setContentsMargins(20, 16, 20, 16)
        kkl.setSpacing(10)
        kh = QLabel("Voice (Kokoro)")
        kh.setObjectName("H2")
        ksub = QLabel(
            "Kokoro is an 82M-parameter neural TTS that runs fully offline on CPU. "
            "Model files are ~340 MB total, downloaded once. "
            "Sounds dramatically better than the Windows system voice."
        )
        ksub.setWordWrap(True)
        ksub.setObjectName("Dim")
        kkl.addWidget(kh)
        kkl.addWidget(ksub)

        self.kokoro_status = QLabel(
            "✅ Kokoro model is ready." if kokoro_tts.is_available()
            else "⚠ Kokoro model not downloaded yet (~340 MB)."
        )
        self.kokoro_status.setObjectName("Dim")
        kkl.addWidget(self.kokoro_status)

        self.kokoro_voice_combo = QComboBox()
        for v in kokoro_tts.list_voices():
            self.kokoro_voice_combo.addItem(v)
        current_v = get_kokoro_voice()
        i = self.kokoro_voice_combo.findText(current_v)
        if i >= 0:
            self.kokoro_voice_combo.setCurrentIndex(i)
        kkl.addWidget(self._row("Voice", self.kokoro_voice_combo))

        self.autoplay_cb = QCheckBox(
            "Auto-narrate lessons, hints, and errors as they appear"
        )
        self.autoplay_cb.setChecked(get_autoplay())
        kkl.addWidget(self.autoplay_cb)

        krow = QHBoxLayout()
        self.btn_kk_dl = QPushButton("⬇ Download Kokoro (~340 MB)")
        self.btn_kk_dl.setObjectName("Primary")
        self.btn_kk_dl.setEnabled(not kokoro_tts.is_available())
        self.btn_kk_test = QPushButton("🔊 Test Kokoro voice")
        self.btn_kk_test.setEnabled(kokoro_tts.is_available())
        krow.addWidget(self.btn_kk_dl)
        krow.addStretch(1)
        krow.addWidget(self.btn_kk_test)
        kkl.addLayout(krow)
        outer.addWidget(kk)

        self.btn_kk_dl.clicked.connect(self._on_kokoro_download)
        self.btn_kk_test.clicked.connect(self._on_kokoro_test)
        self.kokoro_voice_combo.currentTextChanged.connect(self._on_kokoro_voice_change)
        self.autoplay_cb.toggled.connect(lambda v: save_env(autoplay=v))

        self._kk_bridge = _KokoroBridge()
        self._kk_bridge.progress.connect(self._on_kokoro_progress)
        self._kk_bridge.done.connect(self._on_kokoro_done)
        self._kk_bridge.play_ready.connect(self._on_kokoro_play_ready)
        self._kk_bridge.test_error.connect(self._on_kokoro_test_error)

        # ----- Voice control (Vosk) card -----
        vc = QFrame()
        vc.setObjectName("Card")
        vcl = QVBoxLayout(vc)
        vcl.setContentsMargins(20, 16, 20, 16)
        vcl.setSpacing(10)
        vh = QLabel("Voice control")
        vh.setObjectName("H2")
        vsub = QLabel(
            "Talk to PyQuest. Toggle the 🎤 button (or press Ctrl+Space) inside a lesson, "
            "then say things like 'run', 'check answer', 'show hint', 'next', or 'go back'. "
            "Speech recognition is offline (Vosk). The model is ~50 MB and downloads once."
        )
        vsub.setWordWrap(True)
        vsub.setObjectName("Dim")
        vcl.addWidget(vh)
        vcl.addWidget(vsub)

        self.voice_status = QLabel(
            "✅ Speech model is downloaded and ready."
            if model_available()
            else "⚠ Speech model is not downloaded yet."
        )
        self.voice_status.setObjectName("Dim")
        vcl.addWidget(self.voice_status)

        vrow = QHBoxLayout()
        self.btn_dl = QPushButton("⬇ Download speech model (~50 MB)")
        self.btn_dl.setObjectName("Primary")
        self.btn_dl.setEnabled(not model_available())
        vrow.addWidget(self.btn_dl)
        vrow.addStretch(1)
        vcl.addLayout(vrow)
        outer.addWidget(vc)

        rec = get_recognizer()
        rec.model_ready.connect(self._on_model_ready)
        rec.model_download_progress.connect(self._on_dl_progress)
        rec.error_occurred.connect(self._on_rec_error)
        self.btn_dl.clicked.connect(self._on_download_model)

        # ----- LM Studio AI Tutor card -----
        lms = QFrame()
        lms.setObjectName("Card")
        lml = QVBoxLayout(lms)
        lml.setContentsMargins(20, 16, 20, 16)
        lml.setSpacing(10)
        lh = QLabel("AI Tutor (LM Studio)")
        lh.setObjectName("H2")
        lsub = QLabel(
            "PyQuest can call a local LLM running in LM Studio. Open LM Studio, "
            "load a chat model, click 'Start Server'. Then test the connection below. "
            "Inside any lesson, click 🤖 Ask tutor or say 'ask tutor'."
        )
        lsub.setWordWrap(True)
        lsub.setObjectName("Dim")
        lml.addWidget(lh)
        lml.addWidget(lsub)

        self.lms_url_edit = QLineEdit(get_lmstudio_url())
        self.lms_url_edit.setPlaceholderText("http://localhost:1234/v1")
        lml.addWidget(self._row("Base URL", self.lms_url_edit))

        # Model picker: dropdown auto-populated from /v1/models + refresh button.
        model_row_host = QWidget()
        model_row_layout = QHBoxLayout(model_row_host)
        model_row_layout.setContentsMargins(0, 0, 0, 0)
        model_row_layout.setSpacing(8)
        self.lms_model_combo = QComboBox()
        # Non-editable so it's visually obvious it's a dropdown (with arrow).
        # If you need to type a custom model name, do it via .env directly.
        saved_model = get_lmstudio_model()
        if saved_model:
            self.lms_model_combo.addItem(saved_model)
        else:
            self.lms_model_combo.addItem("(click Refresh to fetch loaded models)")
        self.btn_lms_refresh = QPushButton("Refresh")
        self.btn_lms_refresh.setObjectName("Ghost")
        self.btn_lms_refresh.setToolTip("Fetch the list of models currently loaded in LM Studio")
        self.btn_lms_refresh.setFixedWidth(80)
        model_row_layout.addWidget(self.lms_model_combo, 1)
        model_row_layout.addWidget(self.btn_lms_refresh)
        lml.addWidget(self._row("Model", model_row_host))

        self.btn_lms_refresh.clicked.connect(self._on_refresh_models)
        self.lms_model_combo.currentTextChanged.connect(self._on_model_changed)

        self.proactive_cb = QCheckBox(
            "Let the AI tutor jump in automatically on wrong answers and Python errors"
        )
        self.proactive_cb.setChecked(get_proactive_tutor())
        lml.addWidget(self.proactive_cb)

        # Persona picker (populated from data/personas.json)
        from pyquest.services.tutor import list_personas
        self.persona_combo = QComboBox()
        for pid, label in list_personas():
            self.persona_combo.addItem(label, pid)
        current_persona = get_tutor_persona()
        for i in range(self.persona_combo.count()):
            if self.persona_combo.itemData(i) == current_persona:
                self.persona_combo.setCurrentIndex(i)
                break
        lml.addWidget(self._row("Tutor mood", self.persona_combo))
        self.persona_combo.currentIndexChanged.connect(self._on_persona_change)

        lms_row = QHBoxLayout()
        self.btn_lms_test = QPushButton("🔌 Test connection")
        self.btn_lms_test.setObjectName("Ghost")
        self.btn_lms_save = QPushButton("💾 Save")
        self.btn_lms_save.setObjectName("Primary")
        lms_row.addStretch(1)
        lms_row.addWidget(self.btn_lms_test)
        lms_row.addWidget(self.btn_lms_save)
        lml.addLayout(lms_row)

        self.lms_status = QLabel("")
        self.lms_status.setObjectName("Dim")
        self.lms_status.setWordWrap(True)
        lml.addWidget(self.lms_status)

        outer.addWidget(lms)
        self.btn_lms_test.clicked.connect(self._on_test_lmstudio)
        self.btn_lms_save.clicked.connect(self._on_save_lmstudio)
        self.proactive_cb.toggled.connect(lambda v: save_env(proactive=v))

        # ----- About + bug report card -----
        about = QFrame()
        about.setObjectName("Card")
        al = QVBoxLayout(about)
        al.setContentsMargins(20, 16, 20, 16)
        al.setSpacing(10)
        ah = QLabel("About")
        ah.setObjectName("H2")
        ainfo = QLabel(
            f"{APP_NAME} v{APP_VERSION}. A friendly Python learner with voice + an optional local AI tutor.\n"
            "Sandbox: subprocess + AST guard + 5s timeout. Not a security boundary, so "
            "do not paste untrusted code."
        )
        ainfo.setObjectName("Dim")
        ainfo.setWordWrap(True)
        al.addWidget(ah)
        al.addWidget(ainfo)

        privacy = QLabel(
            "Privacy: PyQuest runs fully on your device. No telemetry, no analytics, "
            "no data leaves your computer. Logs live in userdata/logs/ for your own debugging."
        )
        privacy.setObjectName("Dim")
        privacy.setWordWrap(True)
        al.addWidget(privacy)

        about_row = QHBoxLayout()
        self.btn_show_welcome = QPushButton("Show welcome again")
        self.btn_show_welcome.setObjectName("Ghost")
        self.btn_open_logs = QPushButton("Open log folder")
        self.btn_open_logs.setObjectName("Ghost")
        self.btn_report = QPushButton("Report a bug")
        self.btn_report.setObjectName("Ghost")
        about_row.addWidget(self.btn_show_welcome)
        about_row.addWidget(self.btn_open_logs)
        about_row.addWidget(self.btn_report)
        about_row.addStretch(1)
        al.addLayout(about_row)
        outer.addWidget(about)

        self.btn_show_welcome.clicked.connect(self._on_show_welcome)
        self.btn_open_logs.clicked.connect(self._on_open_logs)
        self.btn_report.clicked.connect(self._on_report_bug)

        outer.addStretch(1)

    # ----------------------------------------------------------------
    def _row(self, label: str, widget) -> QWidget:
        from PySide6.QtWidgets import QSizePolicy
        host = QWidget()
        h = QHBoxLayout(host)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        lab = QLabel(label)
        lab.setFixedWidth(90)
        h.addWidget(lab)
        h.addWidget(widget, 1)
        # Never let the row collapse vertically when the page is short on space.
        host.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        host.setMinimumHeight(36)
        return host

    # ---------- Vosk speech model ----------
    def _on_download_model(self) -> None:
        self.btn_dl.setEnabled(False)
        self.voice_status.setText("⏬ Downloading speech model... 0%")
        get_recognizer().ensure_model_async()

    def _on_dl_progress(self, pct: int) -> None:
        self.voice_status.setText(f"⏬ Downloading speech model... {pct}%")

    def _on_model_ready(self) -> None:
        self.voice_status.setText("✅ Speech model is downloaded and ready.")
        self.btn_dl.setEnabled(False)

    def _on_rec_error(self, msg: str) -> None:
        self.voice_status.setText(f"⚠ {msg}")
        self.btn_dl.setEnabled(True)

    # ---------- Kokoro ----------
    def _on_kokoro_download(self) -> None:
        self.btn_kk_dl.setEnabled(False)
        self.kokoro_status.setText("⏬ Downloading Kokoro model... 0%")
        bridge = self._kk_bridge

        def progress(name: str, pct: int) -> None:
            bridge.progress.emit(name, pct)

        def finished(exc) -> None:
            bridge.done.emit("" if exc is None else str(exc))

        kokoro_tts.download_async(progress, finished)

    def _on_kokoro_progress(self, name: str, pct: int) -> None:
        label = "voices" if name == "voices" else "model"
        self.kokoro_status.setText(f"⏬ Downloading Kokoro {label}... {pct}%")

    def _on_kokoro_done(self, err: str) -> None:
        if err:
            self.kokoro_status.setText(f"⚠ Download failed: {err}")
            self.btn_kk_dl.setEnabled(True)
            return
        self.kokoro_status.setText("✅ Kokoro model is ready.")
        self.btn_kk_dl.setEnabled(False)
        self.btn_kk_test.setEnabled(True)

    def _on_kokoro_test(self) -> None:
        if not kokoro_tts.is_available():
            self.kokoro_status.setText("⚠ Download Kokoro first.")
            return
        get_narrator().stop()
        kokoro_tts.stop_playback()
        save_env(kokoro_voice=self.kokoro_voice_combo.currentText())
        self.kokoro_status.setText("🔊 Synthesizing with Kokoro...")
        self.btn_kk_test.setEnabled(False)

        voice = self.kokoro_voice_combo.currentText()
        bridge = self._kk_bridge

        def _job() -> None:
            try:
                samples, sr = kokoro_tts.synthesize(
                    "Hello, I am your Kokoro offline voice. "
                    "If you can hear me, the setup worked.",
                    voice=voice,
                )
                bridge.play_ready.emit(samples, sr)
            except Exception as exc:  # noqa: BLE001
                bridge.test_error.emit(str(exc))

        threading.Thread(target=_job, daemon=True).start()

    def _on_kokoro_play_ready(self, samples, sr: int) -> None:
        self.kokoro_status.setText("🔊 Playing Kokoro test...")
        try:
            kokoro_tts.play(samples, sr)
            self.kokoro_status.setText("✅ Kokoro test finished.")
        except Exception as exc:  # noqa: BLE001
            self.kokoro_status.setText(f"⚠ Playback failed: {exc}")
        finally:
            self.btn_kk_test.setEnabled(True)

    def _on_kokoro_test_error(self, msg: str) -> None:
        self.kokoro_status.setText(f"⚠ Test failed: {msg}")
        self.btn_kk_test.setEnabled(True)

    def _on_kokoro_voice_change(self, voice: str) -> None:
        save_env(kokoro_voice=voice)

    # ---------- Tutor persona ----------
    def _on_persona_change(self) -> None:
        persona = self.persona_combo.currentData() or "friendly"
        save_env(tutor_persona=persona)
        # Reset history so the tone switch is clean.
        from pyquest.services.tutor import get_tutor
        get_tutor().reset_history()

    # ---------- LM Studio ----------
    def _on_save_lmstudio(self) -> None:
        save_env(
            lmstudio_url=self.lms_url_edit.text().strip() or "http://localhost:1234/v1",
            lmstudio_model=self.lms_model_combo.currentText().strip() or "local-model",
            proactive=self.proactive_cb.isChecked(),
        )
        self.lms_status.setText("Saved.")
        self.saved.emit()

    # ---------- Appearance ----------
    def _on_theme_change(self) -> None:
        theme = self.theme_combo.currentData() or "dark"
        save_env(theme=theme)
        # Apply immediately, no restart needed.
        from PySide6.QtWidgets import QApplication

        from pyquest.ui.theme import build_stylesheet
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(theme))

    # ---------- About / bug report ----------
    def _on_show_welcome(self) -> None:
        # Find the MainWindow ancestor and ask it to re-show the wizard.
        win = self.window()
        if hasattr(win, "show_welcome_wizard"):
            win.show_welcome_wizard()

    def _on_open_logs(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from pyquest.logging_setup import LOG_DIR
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR)))

    def _on_report_bug(self) -> None:
        """Open the GitHub Issues page with a pre-filled body containing log tail."""
        import platform
        import urllib.parse

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from pyquest.config import APP_VERSION
        from pyquest.logging_setup import LOG_FILE, tail_log

        body = (
            "## What happened?\n\n"
            "_Describe the bug:_\n\n"
            "## What did you expect?\n\n"
            "_Describe the expected behavior:_\n\n"
            "## Environment\n\n"
            f"- PyQuest: {APP_VERSION}\n"
            f"- OS: {platform.platform()}\n"
            f"- Python: {platform.python_version()}\n\n"
            "## Recent log entries\n\n"
            "```\n"
            f"{tail_log(40)}\n"
            "```\n\n"
            f"_Full log: `{LOG_FILE}`_\n"
        )
        from pyquest.config import GITHUB_REPO_URL
        url = (
            f"{GITHUB_REPO_URL}/issues/new?"
            + urllib.parse.urlencode({"title": "Bug: ", "body": body})
        )
        QDesktopServices.openUrl(QUrl(url))

    def _on_test_lmstudio(self) -> None:
        url = self.lms_url_edit.text().strip() or "http://localhost:1234/v1"
        self.lms_status.setText("Connecting...")
        try:
            models = lmstudio_client.list_models(url)
        except Exception as exc:  # noqa: BLE001
            self.lms_status.setText(
                f"⚠ Couldn't reach LM Studio at {url}.\n"
                f"Open LM Studio → Local Server → Start Server. Error: {exc}"
            )
            return
        if not models:
            self.lms_status.setText(
                "✅ Reached LM Studio, but no model is loaded. Load a chat model and try again."
            )
            return
        self._populate_model_combo(models)
        self.lms_status.setText("✅ Connected. Loaded model(s): " + ", ".join(models[:3]))

    # ---- model dropdown helpers ----
    def _populate_model_combo(self, models: list[str]) -> None:
        """Refresh the combo while preserving the saved selection if still present."""
        current = self.lms_model_combo.currentText().strip()
        self.lms_model_combo.blockSignals(True)
        self.lms_model_combo.clear()
        for m in models:
            self.lms_model_combo.addItem(m)
        # Reselect saved value if still in the list; otherwise pick the first.
        if current and current in models:
            self.lms_model_combo.setCurrentText(current)
        elif models:
            self.lms_model_combo.setCurrentIndex(0)
            # Persist the auto-selected first model.
            save_env(lmstudio_model=models[0])
        self.lms_model_combo.blockSignals(False)

    def _on_refresh_models(self) -> None:
        url = self.lms_url_edit.text().strip() or "http://localhost:1234/v1"
        self.lms_status.setText("Fetching loaded models...")
        self.btn_lms_refresh.setEnabled(False)
        try:
            models = lmstudio_client.list_models(url)
        except Exception as exc:  # noqa: BLE001
            self.lms_status.setText(
                f"⚠ Couldn't reach LM Studio at {url}. Is the server started? ({exc})"
            )
            self.btn_lms_refresh.setEnabled(True)
            return
        self.btn_lms_refresh.setEnabled(True)
        if not models:
            self.lms_status.setText(
                "⚠ Reached LM Studio, but no models are loaded. Load one and click Refresh."
            )
            return
        self._populate_model_combo(models)
        self.lms_status.setText(
            f"✅ Found {len(models)} model(s). Using: {self.lms_model_combo.currentText()}"
        )

    def _on_model_changed(self, text: str) -> None:
        """Persist the picked model immediately so the tutor uses it on the next call."""
        if text.strip():
            save_env(lmstudio_model=text.strip())

    def showEvent(self, event):  # noqa: N802
        """Quietly refresh the model list when the page becomes visible."""
        super().showEvent(event)
        self._quiet_refresh_models()

    def _quiet_refresh_models(self) -> None:
        """Fetch models in the background; silent on failure (don't spam status)."""
        import threading

        url = self.lms_url_edit.text().strip() or "http://localhost:1234/v1"

        def _job() -> None:
            try:
                models = lmstudio_client.list_models(url, timeout=1.5)
            except Exception:  # noqa: BLE001
                return  # server not up; that's fine, user can hit Refresh manually
            if not models:
                return
            # Marshal back to UI thread.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._populate_model_combo(models))

        threading.Thread(target=_job, daemon=True).start()
