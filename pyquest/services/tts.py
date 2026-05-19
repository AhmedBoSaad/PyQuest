"""TTS narration service.

A queue-based narrator with playback controls (play/pause, skip, prev, stop, replay).
Plays in a background thread so the UI stays responsive. Emits Qt signals so the
UI can highlight the current segment.

Voice synthesis is handled by Kokoro (offline, neural). The user picks a voice
in Settings; if the Kokoro model files haven't been downloaded yet, narration
is disabled until they are.
"""
from __future__ import annotations

import logging
import queue
import random
import re
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from pyquest.config import get_kokoro_voice
from pyquest.services import kokoro_tts

log = logging.getLogger(__name__)


@dataclass
class Segment:
    text: str
    label: str = ""  # short tag the UI can show, e.g. "Intro", "Example", "Hint 1"


class TTSNarrator(QObject):
    """Singleton narration engine."""

    # Signals (UI thread)
    segment_started = Signal(int, str, str)  # index, label, text
    segment_finished = Signal(int)
    queue_finished = Signal()
    state_changed = Signal(str)  # "idle" | "playing" | "paused" | "stopped"
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._segments: list[Segment] = []
        self._index: int = -1
        self._thread: threading.Thread | None = None
        self._cmd_queue: queue.Queue[str] = queue.Queue()
        self._pause_evt = threading.Event()
        self._pause_evt.set()  # not paused
        self._stop_evt = threading.Event()
        self._skip_evt = threading.Event()
        self._lock = threading.Lock()
        self._state = "idle"

    # ---------------------------------------------------------------- public
    @property
    def state(self) -> str:
        return self._state

    @property
    def index(self) -> int:
        return self._index

    @property
    def total(self) -> int:
        return len(self._segments)

    def play_text(self, text: str, label: str = "") -> None:
        """Convenience: speak a single chunk now (interrupts current narration)."""
        self.play_segments([Segment(text=text, label=label)])

    def play_segments(self, segments: list[Segment]) -> None:
        """Replace the current queue and start playing from the top."""
        self.stop()
        self._segments = [s for s in segments if (s.text or "").strip()]
        self._index = -1
        if not self._segments:
            return
        self._start_thread()

    def append_segment(self, segment: Segment, *, play_now: bool = False) -> None:
        """Add a segment to the end. If idle and play_now, begin playing."""
        if not (segment.text or "").strip():
            return
        with self._lock:
            self._segments.append(segment)
        if play_now and self._state in ("idle", "stopped"):
            self._start_thread()

    def pause(self) -> None:
        if self._state == "playing":
            self._pause_evt.clear()
            kokoro_tts.stop_playback()
            self._set_state("paused")

    def resume(self) -> None:
        if self._state == "paused":
            self._pause_evt.set()
            self._set_state("playing")

    def toggle_pause(self) -> None:
        if self._state == "playing":
            self.pause()
        elif self._state == "paused":
            self.resume()

    def stop(self) -> None:
        self._stop_evt.set()
        self._pause_evt.set()  # release pause so the thread can exit
        kokoro_tts.stop_playback()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._stop_evt.clear()
        self._skip_evt.clear()
        self._set_state("idle")

    def next(self) -> None:
        """Skip to the next segment in the queue."""
        if self._state in ("playing", "paused"):
            self._skip_evt.set()
            self._pause_evt.set()  # in case paused
            kokoro_tts.stop_playback()

    def prev(self) -> None:
        """Replay the previous segment (or current from start)."""
        with self._lock:
            target = max(0, self._index - 1)
            self._index = target - 1  # next loop tick will increment to target
        self._skip_evt.set()
        self._pause_evt.set()
        kokoro_tts.stop_playback()
        if self._state == "idle":
            self._start_thread()

    def replay(self) -> None:
        """Replay the current segment from the start."""
        with self._lock:
            self._index = max(-1, self._index - 1)
        self._skip_evt.set()
        self._pause_evt.set()
        kokoro_tts.stop_playback()
        if self._state == "idle":
            self._start_thread()

    # ---------------------------------------------------------------- worker
    def _start_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._skip_evt.clear()
        self._pause_evt.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _set_state(self, new: str) -> None:
        if new != self._state:
            self._state = new
            self.state_changed.emit(new)

    def _run_loop(self) -> None:
        self._set_state("playing")
        try:
            while True:
                if self._stop_evt.is_set():
                    break
                with self._lock:
                    self._index += 1
                    if self._index >= len(self._segments):
                        break
                    seg = self._segments[self._index]
                    idx = self._index
                self._skip_evt.clear()
                self.segment_started.emit(idx, seg.label, seg.text)
                self._speak_one(seg.text)
                self.segment_finished.emit(idx)
                if self._stop_evt.is_set():
                    break
            self._set_state("idle")
            if not self._stop_evt.is_set():
                self.queue_finished.emit()
        except Exception as exc:  # noqa: BLE001
            log.exception("Narrator crashed")
            self.error_occurred.emit(str(exc))
            self._set_state("idle")

    def _wait_unpause(self) -> bool:
        """Block while paused. Return False if stopped/skipped during wait."""
        while not self._pause_evt.is_set():
            if self._stop_evt.is_set() or self._skip_evt.is_set():
                return False
            self._pause_evt.wait(timeout=0.1)
        return True

    def _speak_one(self, text: str) -> None:
        if self._stop_evt.is_set() or self._skip_evt.is_set():
            return
        if not self._wait_unpause():
            return

        if not kokoro_tts.is_available():
            self.error_occurred.emit(
                "⚠ Voice model not downloaded. Open Settings → Offline voice (Kokoro) "
                "and click 'Download Kokoro' to enable narration."
            )
            return

        try:
            voice = get_kokoro_voice()
            samples, sr = kokoro_tts.synthesize(text, voice=voice)
            if self._stop_evt.is_set() or self._skip_evt.is_set():
                return
            if not self._wait_unpause():
                return
            kokoro_tts.play(samples, sr)
        except Exception as exc:  # noqa: BLE001
            log.error("Kokoro TTS failed: %s", exc)
            self.error_occurred.emit(f"⚠ Kokoro TTS failed: {exc}")


# ----------------------------------------------------------------- singleton
_INSTANCE: TTSNarrator | None = None


def get_narrator() -> TTSNarrator:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = TTSNarrator()
    return _INSTANCE


# --------------------------------------------------------- text helpers
ENCOURAGEMENTS = [
    "You're doing great. Every single line of code you write makes you stronger.",
    "Mistakes are how programmers learn. Take a breath, read the message, and try again.",
    "Look how far you've come! Keep that momentum going.",
    "You're literally training your brain to think like a computer. That's amazing.",
    "Slow down, read carefully, and trust yourself. You've got this.",
    "Programming is a skill. Skills grow with practice. You're practicing right now.",
    "Don't compare yourself to anyone else. Compare yourself to yesterday's you.",
    "Every great programmer started exactly where you are. Keep going.",
    "Curiosity beats talent. Stay curious and you'll go far.",
    "One step at a time. The next lesson is waiting for you when you're ready.",
]


def encouragement_text() -> str:
    return random.choice(ENCOURAGEMENTS)


def explain_error_text(stderr: str) -> str:
    last = stderr.strip().splitlines()[-1] if stderr.strip() else "no error message"
    return (
        f"Let's look at this Python error together. "
        f"The message says: {last}. "
        f"This usually means a small typo, a missing quote, "
        f"or a name Python doesn't recognise. Read your code line by line and check spelling carefully."
    )


def strip_markdown_for_speech(md: str) -> str:
    """Quick-and-dirty markdown-to-plain so the voice doesn't read symbols out loud."""
    text = md
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ------------------------------------------------ build narration segments
HEADING_RE = re.compile(r"^##+\s+(.+)$", re.MULTILINE)


def build_lesson_segments(lesson) -> list[Segment]:
    """Break a lesson into spoken segments: intro, each ## section, exercise, then encouragement."""
    segs: list[Segment] = []

    intro = (
        f"Lesson {lesson.order}: {lesson.title}. "
        f"{lesson.objective}"
    )
    segs.append(Segment(text=intro, label="Intro"))

    md = lesson.explanation_md or ""
    # Split markdown by ## headings
    parts = re.split(r"(?m)^##+\s+", md)
    if parts and not parts[0].strip() and len(parts) > 1:
        parts = parts[1:]
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        # First line after the heading split is the heading text itself
        lines = part.splitlines()
        head = lines[0].strip() if lines else f"Part {i+1}"
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        # If the original markdown has no headings, parts = [whole text]; handle that
        if i == 0 and not HEADING_RE.search(md):
            spoken = strip_markdown_for_speech(part)
            if spoken:
                segs.append(Segment(text=spoken, label="Explanation"))
            continue
        spoken = strip_markdown_for_speech(body) if body else strip_markdown_for_speech(head)
        if spoken:
            segs.append(Segment(text=spoken, label=head[:40]))

    if lesson.exercise_prompt:
        segs.append(
            Segment(
                text=f"Now your turn. {lesson.exercise_prompt}",
                label="Your task",
            )
        )

    return segs


def hint_segment(hint_index: int, total: int, hint_text: str) -> Segment:
    return Segment(
        text=f"Hint {hint_index} of {total}. {hint_text}",
        label=f"Hint {hint_index}",
    )


def error_segment(stderr: str) -> Segment:
    return Segment(text=explain_error_text(stderr), label="Error help")


def encouragement_segment() -> Segment:
    return Segment(text=encouragement_text(), label="Encouragement")
