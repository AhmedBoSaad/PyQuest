"""Configuration: paths, environment loading, persistent settings."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv, set_key

ROOT_DIR = Path(__file__).resolve().parent.parent
PYQUEST_DIR = ROOT_DIR / "pyquest"
DATA_DIR = PYQUEST_DIR / "data"
LESSONS_DIR = DATA_DIR / "lessons"
BADGES_FILE = DATA_DIR / "badges.json"
USERDATA_DIR = ROOT_DIR / "userdata"
DB_FILE = USERDATA_DIR / "progress.db"
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE_FILE = ROOT_DIR / ".env.example"

USERDATA_DIR.mkdir(exist_ok=True)

if not ENV_FILE.exists() and ENV_EXAMPLE_FILE.exists():
    shutil.copy(ENV_EXAMPLE_FILE, ENV_FILE)

load_dotenv(ENV_FILE)


def get_autoplay() -> bool:
    val = os.getenv("PYQUEST_AUTOPLAY", "1").strip().lower()
    return val in ("1", "true", "yes", "on")


def get_lmstudio_url() -> str:
    return os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1").strip()


def get_lmstudio_model() -> str:
    return os.getenv("LMSTUDIO_MODEL", "local-model").strip()


def get_proactive_tutor() -> bool:
    # Default OFF. LM Studio is optional. The user can opt in from Settings
    # after testing the connection.
    val = os.getenv("PYQUEST_PROACTIVE_TUTOR", "0").strip().lower()
    return val in ("1", "true", "yes", "on")


def get_kokoro_voice() -> str:
    return os.getenv("KOKORO_VOICE", "af_heart").strip()


def get_theme() -> str:
    """'dark' or 'light'."""
    val = os.getenv("PYQUEST_THEME", "dark").strip().lower()
    return "light" if val == "light" else "dark"


def get_tutor_persona() -> str:
    """One of: 'friendly' | 'strict' | 'drill_sergeant'."""
    val = os.getenv("PYQUEST_TUTOR_PERSONA", "friendly").strip().lower()
    if val not in ("friendly", "strict", "drill_sergeant"):
        return "friendly"
    return val


def save_env(
    *,
    autoplay: bool | None = None,
    lmstudio_url: str | None = None,
    lmstudio_model: str | None = None,
    proactive: bool | None = None,
    kokoro_voice: str | None = None,
    tutor_persona: str | None = None,
    theme: str | None = None,
) -> None:
    """Persist settings to .env and refresh the live environment."""
    if not ENV_FILE.exists():
        ENV_FILE.touch()
    if autoplay is not None:
        set_key(str(ENV_FILE), "PYQUEST_AUTOPLAY", "1" if autoplay else "0")
        os.environ["PYQUEST_AUTOPLAY"] = "1" if autoplay else "0"
    if lmstudio_url is not None:
        set_key(str(ENV_FILE), "LMSTUDIO_BASE_URL", lmstudio_url)
        os.environ["LMSTUDIO_BASE_URL"] = lmstudio_url
    if lmstudio_model is not None:
        set_key(str(ENV_FILE), "LMSTUDIO_MODEL", lmstudio_model)
        os.environ["LMSTUDIO_MODEL"] = lmstudio_model
    if proactive is not None:
        set_key(str(ENV_FILE), "PYQUEST_PROACTIVE_TUTOR", "1" if proactive else "0")
        os.environ["PYQUEST_PROACTIVE_TUTOR"] = "1" if proactive else "0"
    if kokoro_voice is not None:
        set_key(str(ENV_FILE), "KOKORO_VOICE", kokoro_voice)
        os.environ["KOKORO_VOICE"] = kokoro_voice
    if tutor_persona is not None:
        set_key(str(ENV_FILE), "PYQUEST_TUTOR_PERSONA", tutor_persona)
        os.environ["PYQUEST_TUTOR_PERSONA"] = tutor_persona
    if theme is not None:
        set_key(str(ENV_FILE), "PYQUEST_THEME", theme)
        os.environ["PYQUEST_THEME"] = theme


EXEC_TIMEOUT_SECONDS = 5
APP_NAME = "PyQuest"
APP_VERSION = "0.1"
# Edit this once you've created the repo. Used by the "Report a bug" button.
GITHUB_REPO_URL = "https://github.com/AhmedBoSaad/PyQuest"
