# Changelog

All notable changes to PyQuest will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1] — 2026-05-19

First public release.

### Added
- **10 hand-written chapters** covering programming basics through lists, plus 5 "coming soon" stubs.
- **PyQuest Studio editorial theme** — warm ink palette, single gold accent, Instrument Serif / Geist / JetBrains Mono type pair.
- **Dark + light themes** swappable from Settings.
- **Built-in code editor** with Python syntax highlighting, line numbers, smart indent.
- **Sandboxed execution** — subprocess + AST guard + 5-second timeout. Blocks dangerous imports, dunder bypasses, and most escape patterns.
- **Offline neural voice** via Kokoro-ONNX (28 voices, ~340 MB model, CPU only).
- **Offline voice commands** via Vosk (~50 MB model). Toggle mic with Ctrl+Space.
- **Optional AI tutor** via local LM Studio, with model picker + Refresh button that auto-fetches `/v1/models`.
- **Three tutor personas**: Friendly, Strict, Drill Sergeant — the last roasts the student with escalating intensity based on mistake count.
- **Gamification**: XP, levels, daily streaks with Duolingo-style streak freezes (1 free per week), animated badge popups.
- **Welcome wizard** on first launch — three skippable steps for voice / speech / tutor setup.
- **Bug report helper** — opens GitHub Issues pre-filled with log tail.
- **Local rotating log** at `userdata/logs/pyquest.log`. Zero telemetry.
- **SQLite schema migrations** so future schema changes survive existing user DBs.
- **JSON lesson validator** with "did you mean…?" hints for typos.
- **Unit tests** for checker, AST guard, command parser, lesson validator.

### Notable architectural decisions
- Onnxruntime is imported before PySide6 to avoid a Windows MSVC DLL conflict.
- Personas live in `pyquest/data/personas.json` — edit/add without touching code.
- Mistake counter is **per-lesson, in-memory only** — resets on lesson change so the drill sergeant rage doesn't carry over.
- LM Studio is fully optional. Default `PYQUEST_PROACTIVE_TUTOR=0` so first-time users aren't surprised.
