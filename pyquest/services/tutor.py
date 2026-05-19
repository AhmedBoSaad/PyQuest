"""AI tutor service backed by LM Studio.

Composes lesson context (objective, expected output, user's code, last error)
into a system + user message pair and streams the reply token-by-token through
Qt signals. Optionally pipes the full reply through the narrator (TTS).
"""
from __future__ import annotations

import json as _json
import logging
import threading
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from pyquest.config import DATA_DIR, get_lmstudio_model, get_lmstudio_url, get_tutor_persona
from pyquest.services import lmstudio_client
from pyquest.services.lmstudio_client import ChatMessage

log = logging.getLogger(__name__)

# ----------------------------------------------------------------- personas
PERSONAS_FILE = DATA_DIR / "personas.json"

# Baked-in fallback so the app still runs if data/personas.json is missing.
_FALLBACK = {
    "_teaching_core": [
        "Hard rules you NEVER break:",
        "1. NEVER write the complete solution. Hints only.",
        "2. Always explain WHY the code is wrong in plain English.",
        "3. Reason about the EXACT code in context, not earlier versions.",
        "4. No markdown headings, bullets, or emojis (replies get read aloud).",
        "5. Keep replies under 120 words unless asked for more.",
    ],
    "personas": {
        "friendly": {
            "label": "Friendly tutor (default)",
            "body": [
                "You are PyQuest, a warm, patient Python tutor for an absolute beginner.",
                "Speak gently. Use short sentences and no jargon."
            ],
        },
    },
}


def _load_personas() -> dict:
    """Load personas from JSON; fall back to baked-in defaults on any error."""
    try:
        with PERSONAS_FILE.open("r", encoding="utf-8") as fh:
            data = _json.load(fh)
        if not isinstance(data, dict) or "personas" not in data:
            raise ValueError("personas.json missing 'personas' key")
        return data
    except (OSError, ValueError, _json.JSONDecodeError) as exc:
        log.warning("Failed to load personas.json (%s); using built-in defaults", exc)
        return _FALLBACK


_PERSONAS_DATA: dict | None = None


def _personas() -> dict:
    global _PERSONAS_DATA
    if _PERSONAS_DATA is None:
        _PERSONAS_DATA = _load_personas()
    return _PERSONAS_DATA


def list_personas() -> list[tuple[str, str]]:
    """Return [(id, label)] in the order they appear in the JSON file."""
    data = _personas()
    return [(pid, info.get("label", pid)) for pid, info in data["personas"].items()]


def system_prompt_for(persona: str) -> str:
    data = _personas()
    core_lines = data.get("_teaching_core") or []
    core = "\n".join(core_lines)
    persona_info = data["personas"].get(persona) or data["personas"].get("friendly")
    body_lines = persona_info.get("body", []) if persona_info else []
    body = "\n".join(body_lines)
    return f"{body}\n\n{core}\n"


@dataclass
class LessonContext:
    title: str = ""
    order: int = 0
    objective: str = ""
    explanation_md: str = ""
    exercise_prompt: str = ""
    expected_output: str = ""
    starter_code: str = ""
    user_code: str = ""
    last_stdout: str = ""
    last_stderr: str = ""
    # "lesson" | "quiz" | "done"
    page: str = "lesson"
    quiz_question: str = ""
    quiz_options: list[str] = field(default_factory=list)
    quiz_progress: str = ""  # e.g. "Question 2 of 3"
    # Lesson-scoped mistake count (Python errors + failed checks). Resets per lesson.
    mistakes: int = 0

    def as_system_block(self) -> str:
        parts = [
            f"Current lesson: {self.order:02d}. {self.title}",
            f"Objective: {self.objective}" if self.objective else "",
            f"Student is currently on the {self.page} screen.",
            self._escalation_line(),
        ]
        if self.page == "lesson":
            if self.exercise_prompt:
                parts.append(f"Exercise: {self.exercise_prompt}")
            if self.expected_output:
                parts.append(f"Expected output: {self.expected_output}")
            if self.user_code.strip():
                parts.append(
                    "Student's current code (this is what they have typed RIGHT NOW; "
                    "always reason about THIS code, not earlier versions):\n"
                    f"```python\n{self.user_code.strip()}\n```"
                )
            else:
                parts.append("Student's editor is empty.")
            if self.last_stdout.strip():
                parts.append(f"Their last output: {self.last_stdout.strip()[:400]}")
            if self.last_stderr.strip():
                parts.append(f"Their last error: {self.last_stderr.strip()[:400]}")
        elif self.page == "quiz":
            if self.quiz_progress:
                parts.append(f"Quiz progress: {self.quiz_progress}")
            if self.quiz_question:
                parts.append(f"Quiz question: {self.quiz_question}")
            if self.quiz_options:
                opts = "\n".join(
                    f"  ({chr(ord('A')+i)}) {o}" for i, o in enumerate(self.quiz_options)
                )
                parts.append(f"Options:\n{opts}")
            parts.append(
                "On the quiz screen, do NOT propose new coding exercises. "
                "Help the student reason about the current question without giving the answer."
            )
        elif self.page == "done":
            parts.append(
                "The student just finished this lesson. They can move to the next lesson "
                "or go back to the learning path. Do not invent new exercises."
            )
        return "\n".join(p for p in parts if p)

    def _escalation_line(self) -> str:
        """Tell the LLM how patient/agitated to be, based on mistakes this lesson."""
        n = max(0, int(self.mistakes))
        if n == 0:
            tier = "Mistake count this lesson: 0. Fresh start. Calm baseline tone."
        elif n == 1:
            tier = (
                "Mistake count this lesson: 1. First slip, mild irritation. "
                "Light ribbing, still teaching."
            )
        elif n == 2:
            tier = (
                "Mistake count this lesson: 2. Visibly annoyed. Sigh audibly in text. "
                "Dial up the sarcasm by one notch."
            )
        elif n == 3:
            tier = (
                "Mistake count this lesson: 3. Real exasperation. Stronger language allowed. "
                "Mock the SPECIFIC bug, not the human. Hint must still be present and useful."
            )
        elif n == 4:
            tier = (
                "Mistake count this lesson: 4. Genuinely fed up. Theatrical despair. "
                "More profanity acceptable. Hint must still be present."
            )
        else:
            tier = (
                f"Mistake count this lesson: {n}. Maximum rage mode. "
                "Pretend you're about to retire over this. "
                "Lean into the bit hard: long-suffering, dramatic, mock-furious. "
                "Crucially: STILL TEACH. Even at max anger, the reply MUST end with a concrete, "
                "actionable hint at the specific bug. No solution code."
            )
        return f"[Escalation state] {tier}"


class TutorService(QObject):
    """Stream chat with LM Studio."""

    started = Signal()
    delta = Signal(str)        # token chunk
    finished = Signal(str)     # full text
    failed = Signal(str)
    speak_requested = Signal(str)  # ask the narrator to read this text

    def __init__(self) -> None:
        super().__init__()
        self._history: list[ChatMessage] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._mistakes: int = 0

    # ----------------------------------------------------------------- public
    def reset_history(self) -> None:
        with self._lock:
            self._history = []

    def reset_mistakes(self) -> None:
        with self._lock:
            self._mistakes = 0

    def bump_mistakes(self, by: int = 1) -> int:
        with self._lock:
            self._mistakes = max(0, self._mistakes + by)
            return self._mistakes

    @property
    def mistakes(self) -> int:
        return self._mistakes

    def set_lesson_context(self, ctx: LessonContext) -> None:
        """Replace the lesson context (used as the second system message)."""
        self._lesson_ctx = ctx

    def ask(self, user_text: str, *, speak_reply: bool = True) -> None:
        """Send a user message and stream the reply. Cancels any in-flight call."""
        text = (user_text or "").strip()
        if not text:
            return
        self.cancel()
        with self._lock:
            self._history.append(ChatMessage("user", text))
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(speak_reply,),
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._cancel.clear()

    # ------------------------------------------------------------- background
    def _build_messages(self) -> list[ChatMessage]:
        persona = get_tutor_persona()
        msgs: list[ChatMessage] = [ChatMessage("system", system_prompt_for(persona))]
        ctx_block = ""
        ctx = getattr(self, "_lesson_ctx", None)
        if ctx is not None:
            # Always sync the mistake count from the service so the escalation
            # tier reflects the latest count regardless of caller-side staleness.
            ctx.mistakes = self._mistakes
            ctx_block = ctx.as_system_block()
        if ctx_block:
            msgs.append(ChatMessage("system", ctx_block))
        # Last 12 turns of history is plenty for tutoring.
        with self._lock:
            msgs.extend(self._history[-12:])
        return msgs

    def _run(self, speak_reply: bool) -> None:
        self.started.emit()
        url = get_lmstudio_url()
        model = get_lmstudio_model()
        messages = self._build_messages()
        full = ""
        try:
            for chunk in lmstudio_client.stream_chat(url, model, messages):
                if self._cancel.is_set():
                    break
                full += chunk
                self.delta.emit(chunk)
        except Exception as exc:  # noqa: BLE001
            log.exception("Tutor request failed")
            msg = self._friendly_error(exc)
            self.failed.emit(msg)
            return

        full = full.strip()
        if not full:
            self.failed.emit("The tutor returned an empty reply. Is a model loaded in LM Studio?")
            return

        with self._lock:
            self._history.append(ChatMessage("assistant", full))
        self.finished.emit(full)
        if speak_reply:
            self.speak_requested.emit(full)

    def _friendly_error(self, exc: Exception) -> str:
        text = str(exc)
        if "Connection refused" in text or "Failed to establish" in text or "Max retries" in text:
            return (
                "Couldn't reach LM Studio. Open LM Studio, load a model, "
                "click 'Start Server', then try again."
            )
        if "404" in text:
            return "LM Studio reachable, but the request 404'd. Check the model name in Settings."
        if "401" in text or "403" in text:
            return "LM Studio rejected the request. Check the API URL in Settings."
        return f"Tutor request failed: {text[:200]}"


# ---------- singleton ----------
_INSTANCE: TutorService | None = None


def get_tutor() -> TutorService:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = TutorService()
    return _INSTANCE
