"""Offline speech recognition with Vosk.

Toggle-on / toggle-off architecture:
  - listening = False (default): mic is closed, no audio captured.
  - listening = True: mic is opened, audio streamed to Vosk in real time.
    Whenever Vosk finalises a phrase (small silence), we emit `phrase_recognized`.
    The mic stays open until the user toggles it off.

The Vosk model is auto-downloaded to userdata/vosk-model on first use.
"""
from __future__ import annotations

import json
import logging
import queue
import shutil
import threading
import urllib.request
import zipfile

from PySide6.QtCore import QObject, Signal

from pyquest.config import USERDATA_DIR

log = logging.getLogger(__name__)

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_DIR_NAME = "vosk-model-small-en-us-0.15"
MODEL_PARENT = USERDATA_DIR / "vosk"
MODEL_PATH = MODEL_PARENT / MODEL_DIR_NAME
SAMPLE_RATE = 16000
BLOCK_SIZE = 4000  # ~250ms at 16kHz mono


def model_available() -> bool:
    return MODEL_PATH.is_dir() and (MODEL_PATH / "conf").exists()


def download_model(progress_cb=None) -> None:
    """Download + unzip the Vosk small English model. Idempotent."""
    if model_available():
        return
    MODEL_PARENT.mkdir(parents=True, exist_ok=True)
    zip_path = MODEL_PARENT / "model.zip"

    def _hook(blocks, block_size, total):
        if progress_cb and total > 0:
            done = min(blocks * block_size, total)
            progress_cb(int(100 * done / total))

    log.info("Downloading Vosk model...")
    urllib.request.urlretrieve(VOSK_MODEL_URL, zip_path, _hook)
    log.info("Extracting Vosk model...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(MODEL_PARENT)
    zip_path.unlink(missing_ok=True)
    if not model_available():
        # Some zips extract with slightly different names; find the model dir.
        for child in MODEL_PARENT.iterdir():
            if child.is_dir() and (child / "conf").exists():
                if child.name != MODEL_DIR_NAME:
                    target = MODEL_PARENT / MODEL_DIR_NAME
                    if target.exists():
                        shutil.rmtree(target)
                    child.rename(target)
                break


class SpeechRecognizer(QObject):
    """Toggle-style microphone listener."""

    listening_started = Signal()
    listening_stopped = Signal()
    partial_recognized = Signal(str)
    phrase_recognized = Signal(str)
    error_occurred = Signal(str)
    model_download_progress = Signal(int)
    model_ready = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._listening = False
        self._stop_evt = threading.Event()
        self._thread: threading.Thread | None = None
        self._model = None
        self._lock = threading.Lock()

    @property
    def listening(self) -> bool:
        return self._listening

    # ---------------------------------------------------------- public API
    def ensure_model(self) -> bool:
        """Synchronous check; returns True if model is ready."""
        return model_available()

    def ensure_model_async(self) -> None:
        """Kick off download if needed."""
        if model_available():
            self.model_ready.emit()
            return

        def _job() -> None:
            try:
                download_model(self.model_download_progress.emit)
                self.model_ready.emit()
            except Exception as exc:  # noqa: BLE001
                log.exception("Model download failed")
                self.error_occurred.emit(f"Model download failed: {exc}")

        threading.Thread(target=_job, daemon=True).start()

    def toggle(self) -> None:
        if self._listening:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        with self._lock:
            if self._listening:
                return
            if not model_available():
                self.error_occurred.emit(
                    "Speech model not yet downloaded. Open Settings to download it."
                )
                return
            self._stop_evt.clear()
            self._listening = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.listening_started.emit()

    def stop(self) -> None:
        with self._lock:
            if not self._listening:
                return
            self._stop_evt.set()
            self._listening = False
        # Don't join from UI thread on shutdown; the thread will exit on its own.
        self.listening_stopped.emit()

    # ---------------------------------------------------------- worker
    def _load_model(self):
        if self._model is None:
            from vosk import Model, SetLogLevel

            SetLogLevel(-1)
            self._model = Model(str(MODEL_PATH))
        return self._model

    def _run(self) -> None:
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Audio import failed: {exc}")
            self._listening = False
            self.listening_stopped.emit()
            return

        try:
            model = self._load_model()
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Could not load speech model: {exc}")
            self._listening = False
            self.listening_stopped.emit()
            return

        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(False)

        audio_q: queue.Queue[bytes] = queue.Queue()

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            if status:
                log.debug("audio status: %s", status)
            audio_q.put(bytes(indata))

        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while not self._stop_evt.is_set():
                    try:
                        data = audio_q.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = (result.get("text") or "").strip()
                        if text:
                            self.phrase_recognized.emit(text)
                    else:
                        partial = json.loads(recognizer.PartialResult())
                        ptext = (partial.get("partial") or "").strip()
                        if ptext:
                            self.partial_recognized.emit(ptext)
            # Flush trailing audio when toggled off.
            tail = json.loads(recognizer.FinalResult())
            tail_text = (tail.get("text") or "").strip()
            if tail_text:
                self.phrase_recognized.emit(tail_text)
        except Exception as exc:  # noqa: BLE001
            log.exception("Mic stream failed")
            self.error_occurred.emit(f"Microphone error: {exc}")
        finally:
            self._listening = False
            self.listening_stopped.emit()


# ---------- singleton ----------
_INSTANCE: SpeechRecognizer | None = None


def get_recognizer() -> SpeechRecognizer:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SpeechRecognizer()
    return _INSTANCE
