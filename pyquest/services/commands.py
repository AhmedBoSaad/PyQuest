"""Map recognized speech to lesson actions.

Returns one of these command tags:
  - run            (run the code)
  - check          (run + auto-check)
  - hint           (reveal next hint)
  - next           (advance lesson / next quiz question)
  - back           (back to learning path)
  - retry          (reset the editor / try again)
  - repeat         (replay the current narration segment)
  - skip           (skip current narration segment)
  - stop           (stop narration)
  - pause / resume
  - read           (read the lesson aloud)
  - encourage
  - explain_error
  - quiz_pick:N    (pick option index N for current quiz question)
  - yes / no       (generic affirmation/negation, used after the tutor asks)

If nothing matches, returns ``None`` and the caller should ignore.
"""
from __future__ import annotations

import re

# Order matters: longer phrases first.
COMMAND_PATTERNS: list[tuple[str, list[str]]] = [
    ("ask_tutor", [
        r"\bask (?:the )?tutor\b",
        r"\bopen (?:the )?tutor\b",
        r"\btalk to (?:the )?tutor\b",
        r"\b(?:ai|chat) tutor\b",
        r"\bopen chat\b",
    ]),
    ("close_tutor", [
        r"\bclose (?:the )?tutor\b",
        r"\bclose chat\b",
        r"\bhide (?:the )?tutor\b",
    ]),
    ("check", [
        r"\bcheck (?:my )?(?:answer|code|work)\b",
        r"\bcheck answer\b",
        r"\bcheck it\b",
        r"\bsubmit\b",
    ]),
    ("run", [
        r"\brun (?:the |my )?code\b",
        r"\brun it\b",
        r"\brun\b",
        r"\bexecute\b",
    ]),
    ("hint", [
        r"\b(?:show|give|need) (?:me )?(?:a )?hint\b",
        r"\bhint\b",
        r"\bhelp(?: me)?\b",
    ]),
    ("next", [
        r"\bnext (?:lesson|question|one|step)\b",
        r"\bcontinue\b",
        r"\bmove on\b",
        r"\bgo on\b",
        r"\bnext\b",
        r"\bproceed\b",
    ]),
    ("back", [
        r"\bgo back\b",
        r"\bback to (?:path|menu|lessons?)\b",
        r"\bback\b",
        r"\bexit\b",
        r"\bquit\b",
    ]),
    ("retry", [
        r"\btry again\b",
        r"\breset\b",
        r"\bclear\b",
        r"\bstart over\b",
    ]),
    ("repeat", [
        r"\brepeat (?:that|it|the (?:lesson|part))?\b",
        r"\bsay (?:that |it )?again\b",
        r"\bagain\b",
        r"\bone more time\b",
    ]),
    ("read", [
        r"\bread (?:the )?lesson\b",
        r"\bread it\b",
        r"\bnarrate\b",
        r"\bplay\b",
    ]),
    ("skip", [
        r"\bskip\b",
        r"\bnext segment\b",
    ]),
    ("stop", [
        r"\bstop (?:talking|speaking|narration|reading)?\b",
        r"\bbe quiet\b",
        r"\bshut up\b",  # forgivable, beginners frustrate
        r"\bsilence\b",
    ]),
    ("pause", [
        r"\bpause\b",
        r"\bhold on\b",
        r"\bwait\b",
    ]),
    ("resume", [
        r"\bresume\b",
        r"\bkeep (?:going|reading)\b",
        r"\bgo on\b",
    ]),
    ("encourage", [
        r"\bencourage (?:me)?\b",
        r"\bmotivat(?:e|ion)\b",
        r"\bcheer me up\b",
    ]),
    ("explain_error", [
        r"\bexplain (?:the |my |this )?error\b",
        r"\bwhat(?:'s| is) (?:the |this )?error\b",
        r"\bwhy (?:did )?(?:it|that) fail\b",
        r"\bhelp with error\b",
    ]),
    ("yes", [
        r"\byes\b", r"\byeah\b", r"\byep\b", r"\bsure\b", r"\bokay\b", r"\bok\b",
        r"\bplease (?:do|continue)\b", r"\baffirmative\b",
    ]),
    ("no", [
        r"\bno\b", r"\bnope\b", r"\bnot yet\b", r"\bnegative\b", r"\bcancel\b",
    ]),
]

QUIZ_PICK_WORDS = {
    "first": 0, "one": 0, "1": 0, "a": 0,
    "second": 1, "two": 1, "2": 1, "b": 1,
    "third": 2, "three": 2, "3": 2, "c": 2,
    "fourth": 3, "four": 3, "4": 3, "d": 3,
}


def parse_command(utterance: str) -> tuple[str, dict] | None:
    """Return (command_tag, params) or None."""
    if not utterance:
        return None
    text = utterance.lower().strip()

    # quiz pick: "option B", "answer 2", "pick three", "the second one"
    m = re.search(
        r"\b(?:option|answer|choice|pick|select|choose)\s+(?:the\s+)?(\w+)"
        r"|\bthe\s+(\w+)\s+one\b",
        text,
    )
    if m:
        word = (m.group(1) or m.group(2) or "").strip(".,!? ")
        if word in QUIZ_PICK_WORDS:
            return ("quiz_pick", {"index": QUIZ_PICK_WORDS[word]})

    # bare quiz pick: "two", "three", "b", etc.
    bare = text.strip(".,!? ")
    if bare in QUIZ_PICK_WORDS:
        return ("quiz_pick", {"index": QUIZ_PICK_WORDS[bare]})

    for tag, patterns in COMMAND_PATTERNS:
        for pat in patterns:
            if re.search(pat, text):
                return (tag, {})

    return None
