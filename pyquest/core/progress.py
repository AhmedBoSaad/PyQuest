"""SQLite-backed progress: XP, streak, completed lessons, badges, counters."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from pyquest.config import DB_FILE

XP_PER_LEVEL = 200


class Progress:
    # Bump this whenever you add a new migration step in MIGRATIONS below.
    SCHEMA_VERSION = 2

    def __init__(self) -> None:
        self.conn = sqlite3.connect(str(DB_FILE))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._run_migrations()

    # ------------------------------------------------------------------ schema
    def _init_schema(self) -> None:
        c = self.conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS completed_lessons (
                lesson_id TEXT PRIMARY KEY,
                completed_at TEXT NOT NULL,
                quiz_score INTEGER DEFAULT 0,
                quiz_total INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS badges (
                badge_id TEXT PRIMARY KEY,
                earned_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS counters (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self.conn.commit()
        # seed defaults
        for k, v in (("xp", "0"), ("streak", "0"), ("last_completion_date", "")):
            c.execute("INSERT OR IGNORE INTO state(key, value) VALUES(?, ?)", (k, v))
        self.conn.commit()

    # ---- migrations ----
    def _current_version(self) -> int:
        row = self.conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        if row is None:
            return 1  # pre-migration databases are v1
        try:
            return int(row["value"])
        except (TypeError, ValueError):
            return 1

    def _set_version(self, n: int) -> None:
        self.conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(n),),
        )
        self.conn.commit()

    def _run_migrations(self) -> None:
        v = self._current_version()
        # v1 -> v2: add streak_freezes column + seed.
        if v < 2:
            self.conn.execute(
                "INSERT OR IGNORE INTO state(key, value) VALUES('streak_freezes', '1')"
            )
            self.conn.commit()
            v = 2
            self._set_version(v)

    # ---------- generic state ----------
    def _get(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def _set(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO state(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # ---------- xp / level ----------
    @property
    def xp(self) -> int:
        return int(self._get("xp", "0") or 0)

    def add_xp(self, amount: int) -> int:
        new_xp = max(0, self.xp + amount)
        self._set("xp", str(new_xp))
        return new_xp

    @property
    def level(self) -> int:
        return 1 + self.xp // XP_PER_LEVEL

    @property
    def xp_into_level(self) -> int:
        return self.xp % XP_PER_LEVEL

    @property
    def xp_for_next_level(self) -> int:
        return XP_PER_LEVEL

    # ---------- streak ----------
    # ---------- streak (with Duolingo-style freeze) ----------
    @property
    def streak(self) -> int:
        """Current visible streak. Considers freeze consumption lazily on read."""
        last = self._get("last_completion_date", "")
        if not last:
            return 0
        try:
            last_date = datetime.strptime(last, "%Y-%m-%d").date()
        except ValueError:
            return 0
        delta_days = (date.today() - last_date).days
        if delta_days <= 1:
            return int(self._get("streak", "0") or 0)
        # User missed days. Can a freeze cover *exactly* one missed day?
        if delta_days == 2 and self.streak_freezes > 0:
            return int(self._get("streak", "0") or 0)
        return 0

    @property
    def streak_freezes(self) -> int:
        return int(self._get("streak_freezes", "0") or 0)

    def _consume_freeze(self) -> None:
        n = max(0, self.streak_freezes - 1)
        self._set("streak_freezes", str(n))

    def grant_freeze(self, n: int = 1) -> None:
        self._set("streak_freezes", str(self.streak_freezes + n))

    def _refill_freezes_if_due(self) -> None:
        """Top up to 1 freeze every Monday, max 2 stored."""
        today = date.today()
        last_refill = self._get("last_freeze_refill", "")
        try:
            last_dt = datetime.strptime(last_refill, "%Y-%m-%d").date() if last_refill else None
        except ValueError:
            last_dt = None
        # Refill once per ISO week, on the first lesson completion of that week.
        this_monday = today - timedelta(days=today.weekday())
        if last_dt is None or last_dt < this_monday:
            if self.streak_freezes < 2:
                self.grant_freeze(1)
            self._set("last_freeze_refill", this_monday.isoformat())

    def _bump_streak_for_today(self) -> None:
        today = date.today()
        last = self._get("last_completion_date", "")
        current = int(self._get("streak", "0") or 0)

        # Weekly freeze top-up.
        self._refill_freezes_if_due()

        if not last:
            new_streak = 1
        else:
            try:
                last_date = datetime.strptime(last, "%Y-%m-%d").date()
            except ValueError:
                last_date = today
            delta = (today - last_date).days
            if delta == 0:
                new_streak = max(current, 1)
            elif delta == 1:
                new_streak = current + 1
            elif delta == 2 and self.streak_freezes > 0:
                # Missed exactly one day; freeze covers it.
                self._consume_freeze()
                new_streak = current + 1  # treat as if they completed yesterday too
            else:
                new_streak = 1

        self._set("streak", str(new_streak))
        self._set("last_completion_date", today.isoformat())

    # ---------- completion ----------
    # ---- first-run flag ----
    @property
    def first_run_done(self) -> bool:
        return self._get("first_run_done", "0") == "1"

    def mark_first_run_done(self) -> None:
        self._set("first_run_done", "1")

    def is_completed(self, lesson_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM completed_lessons WHERE lesson_id=?", (lesson_id,)
        ).fetchone()
        return row is not None

    def completed_lesson_ids(self) -> set[str]:
        return {r["lesson_id"] for r in self.conn.execute("SELECT lesson_id FROM completed_lessons")}

    def mark_completed(self, lesson_id: str, quiz_score: int = 0, quiz_total: int = 0) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO completed_lessons(lesson_id, completed_at, quiz_score, quiz_total) "
            "VALUES(?, ?, ?, ?)",
            (lesson_id, datetime.utcnow().isoformat(), quiz_score, quiz_total),
        )
        self.conn.commit()
        self._bump_streak_for_today()

    # ---------- badges ----------
    def has_badge(self, badge_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM badges WHERE badge_id=?", (badge_id,)
        ).fetchone() is not None

    def earn_badge(self, badge_id: str) -> bool:
        if self.has_badge(badge_id):
            return False
        self.conn.execute(
            "INSERT INTO badges(badge_id, earned_at) VALUES(?, ?)",
            (badge_id, datetime.utcnow().isoformat()),
        )
        self.conn.commit()
        return True

    def earned_badge_ids(self) -> set[str]:
        return {r["badge_id"] for r in self.conn.execute("SELECT badge_id FROM badges")}

    # ---------- counters ----------
    def increment_counter(self, name: str, by: int = 1) -> int:
        self.conn.execute(
            "INSERT INTO counters(name, value) VALUES(?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value=value+excluded.value",
            (name, by),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()
        return int(row["value"]) if row else 0

    def get_counter(self, name: str) -> int:
        row = self.conn.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()
        return int(row["value"]) if row else 0

    # ---------- badge evaluation ----------
    def evaluate_badges(self, all_badges: Iterable[dict]) -> list[dict]:
        """Award any newly earned badges; return the list of *newly* awarded badge dicts."""
        newly = []
        completed = self.completed_lesson_ids()
        for badge in all_badges:
            if self.has_badge(badge["id"]):
                continue
            criteria = badge.get("criteria", {})
            ctype = criteria.get("type")
            ok = False
            if ctype == "complete_lesson":
                ok = criteria["lesson_id"] in completed
            elif ctype == "complete_count":
                ok = len(completed) >= int(criteria["count"])
            elif ctype == "streak":
                ok = self.streak >= int(criteria["days"])
            elif ctype == "counter":
                ok = self.get_counter(criteria["name"]) >= int(criteria["value"])
            if ok and self.earn_badge(badge["id"]):
                newly.append(badge)
        return newly
