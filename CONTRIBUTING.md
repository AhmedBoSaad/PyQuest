# Contributing to PyQuest

Thanks for considering a contribution! PyQuest is a hobby project at heart, but issues, PRs, lesson submissions, and tutor personas are all very welcome.

## Quick start

```bash
git clone https://github.com/AhmedBoSaad/PyQuest.git
cd pyquest
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev]"
python run.py
```

## Conventions

- **Python 3.10+.** We use modern syntax: `X | None`, `match`, `:=`.
- **Style:** [`ruff`](https://docs.astral.sh/ruff/). Run `ruff check pyquest` before submitting.
- **Tests:** new logic in `pyquest/core/` or `pyquest/services/` should come with a unit test in `tests/`. Run `pytest`.
- **Commits:** present-tense, imperative ("Add streak freeze", not "Added").

## What to contribute

### Lessons

The biggest win. Drop a JSON file in `pyquest/data/lessons/` following the schema in the README. The validator will tell you about missing fields with friendly hints. Order numbers should be unique and sequential, so pick the next free integer.

### Tutor personas

Edit `pyquest/data/personas.json` and add an entry under `personas`. Each persona has:

- `label`: what shows in the Settings dropdown
- `body`: list of lines that get joined into the system prompt

The "teaching core" rules (never write the solution, no markdown headings, etc.) are appended automatically to every persona so you don't need to repeat them.

### Bug reports

Open an [Issue](../../issues). The app has a **Report a bug** button in Settings that pre-fills the GitHub issue body with your recent log tail. Please use it.

### Code

PRs against `main` are fine. For anything bigger than a small fix, please open an issue first so we can discuss the approach.

## Architecture in 30 seconds

```
run.py
  └─ pyquest.app.main()
       ├─ pyquest.logging_setup       : local rotating logger
       ├─ pyquest.ui.main_window      : QMainWindow, sidebar, topbar, page stack
       │    ├─ pages/dashboard, learning_path, lesson_view, quiz_view, settings_view
       │    └─ widgets/code_editor, console, xp_bar, badge_popup,
       │       mic_button, narration_bar, tutor_drawer, welcome_wizard
       ├─ pyquest.core                : runner, ast_guard, checker, progress (SQLite),
       │                                lesson_loader (+ validator)
       └─ pyquest.services            : tts (Kokoro narrator), kokoro_tts, speech (Vosk),
                                        commands (utterance parser), tutor (LLM), lmstudio_client
```

State lives in `userdata/`:
- `progress.db`: SQLite with schema migrations
- `logs/pyquest.log`: rotating local log
- `kokoro/` and `vosk/`: downloaded models

## Releasing (maintainers)

1. Bump `APP_VERSION` in `pyquest/config.py` and the version in `pyproject.toml`.
2. Update `CHANGELOG.md`.
3. `git tag v1.x.y && git push --tags`.
4. Draft a GitHub Release from the tag, copy the changelog section into the body.

## Code of conduct

Be kind. The Drill Sergeant persona is for the AI tutor only; humans get warm.
