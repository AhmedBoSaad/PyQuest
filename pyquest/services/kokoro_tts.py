"""Offline neural TTS via kokoro-onnx.

Lightweight Kokoro-82M model in ONNX runtime. ~340 MB of model files total,
auto-downloaded to userdata/kokoro/ on first use. No PyTorch needed.

Public surface:
    is_available()          -> True if files are present on disk
    download_async(cb)      -> kick off background download with progress
    synthesize(text, voice) -> (samples_float32, sample_rate)
    play(samples, sr)       -> blocking playback through sounddevice
    list_voices()           -> list[str]
"""
from __future__ import annotations

import logging
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path

import numpy as np

from pyquest.config import USERDATA_DIR

log = logging.getLogger(__name__)

MODEL_DIR = USERDATA_DIR / "kokoro"
MODEL_FILE = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_FILE = MODEL_DIR / "voices-v1.0.bin"

# Official mirror used by kokoro-onnx releases.
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

DEFAULT_VOICE = "af_heart"
SAMPLE_RATE = 24000

# Static voice list (matches the file shipped in voices-v1.0.bin).
# Hard-coded so we can populate Settings without instantiating the model.
KNOWN_VOICES: list[str] = [
    # American English: Female
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    # American English: Male
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael",
    "am_onyx", "am_puck", "am_santa",
    # British English: Female
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    # British English: Male
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
]


def is_available() -> bool:
    return MODEL_FILE.exists() and VOICES_FILE.exists()


def _download_file(url: str, dest: Path, progress_cb: Callable[[int], None] | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    def hook(blocks: int, block_size: int, total: int) -> None:
        if progress_cb and total > 0:
            done = min(blocks * block_size, total)
            progress_cb(int(100 * done / total))

    urllib.request.urlretrieve(url, tmp, hook)
    tmp.replace(dest)


def download(progress_cb: Callable[[str, int], None] | None = None) -> None:
    """Download both files synchronously. progress_cb(filename, percent)."""
    if not MODEL_FILE.exists():
        log.info("Downloading Kokoro model (~310 MB)...")
        _download_file(
            MODEL_URL,
            MODEL_FILE,
            (lambda p: progress_cb("model", p)) if progress_cb else None,
        )
    if not VOICES_FILE.exists():
        log.info("Downloading Kokoro voices (~27 MB)...")
        _download_file(
            VOICES_URL,
            VOICES_FILE,
            (lambda p: progress_cb("voices", p)) if progress_cb else None,
        )


def download_async(progress_cb: Callable[[str, int], None] | None = None,
                   done_cb: Callable[[Exception | None], None] | None = None) -> None:
    def _job() -> None:
        try:
            download(progress_cb)
            if done_cb:
                done_cb(None)
        except Exception as exc:  # noqa: BLE001
            log.exception("Kokoro download failed")
            if done_cb:
                done_cb(exc)

    threading.Thread(target=_job, daemon=True).start()


# ---------- Inference singleton ----------
_engine = None
_engine_lock = threading.Lock()


def _get_engine():
    """Lazy-load the ONNX engine once."""
    global _engine
    with _engine_lock:
        if _engine is None:
            if not is_available():
                raise RuntimeError(
                    "Kokoro model files are missing. Download them from Settings first."
                )
            from kokoro_onnx import Kokoro

            _engine = Kokoro(str(MODEL_FILE), str(VOICES_FILE))
        return _engine


def synthesize(text: str, voice: str = DEFAULT_VOICE) -> tuple[np.ndarray, int]:
    """Return (float32 samples, sample_rate). Raises if model isn't ready."""
    engine = _get_engine()
    samples, sr = engine.create(text, voice=voice or DEFAULT_VOICE, speed=1.0, lang="en-us")
    return samples, sr


def play(samples: np.ndarray, sr: int) -> None:
    """Block until playback finishes."""
    import sounddevice as sd

    sd.stop()
    sd.play(samples, sr)
    sd.wait()


def stop_playback() -> None:
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:  # noqa: BLE001
        pass


def list_voices() -> list[str]:
    return list(KNOWN_VOICES)
