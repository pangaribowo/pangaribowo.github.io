"""SQLite persistence: vacancy history, change detection, application tracker.

Keeping a local DB is what turns a one-off scraper into a system: it lets us
detect *new* postings between runs, watch applicant counts climb, and remember
which vacancies the user already applied to or dismissed.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import Vacancy

SCHEMA = """
CREATE TABLE IF NOT EXISTS vacancies (
    id              TEXT PRIMARY KEY,
    position        TEXT,
    company         TEXT,
    city            TEXT,
    province        TEXT,
    province_code   TEXT,
    quota           INTEGER,
    registered      INTEGER,
    majors          TEXT,
    levels          TEXT,
    deadline        TEXT,
    is_government   INTEGER,
    payload         TEXT NOT NULL,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id    TEXT NOT NULL,
    registered    INTEGER,
    quota         INTEGER,
    captured_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    vacancy_id   TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'shortlisted',
    score        REAL,
    note         TEXT DEFAULT '',
    letter_path  TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT,
    total       INTEGER,
    new_count   INTEGER,
    started_at  TEXT,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_vac_province ON vacancies(province_code);
CREATE INDEX IF NOT EXISTS idx_vac_deadline ON vacancies(deadline);
CREATE INDEX IF NOT EXISTS idx_snap_vac     ON snapshots(vacancy_id);
"""

VALID_STATUSES = (
    "shortlisted", "letter_ready", "applied", "interview",
    "accepted", "rejected", "skipped",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path = "magangku.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    def upsert_many(self, vacancies: list[Vacancy]) -> dict[str, Any]:
        """Insert/update vacancies. Returns new + changed ids."""
        now = _now()
        new_ids: list[str] = []
        changed: list[dict[str, Any]] = []

        with self.connect() as conn:
            for v in vacancies:
                row = conn.execute(
                    "SELECT id, registered, quota FROM vacancies WHERE id = ?", (v.id,)
                ).fetchone()

                payload = v.to_json()
                deadline = v.deadline.isoformat() if v.deadline else None

                if row is None:
                    new_ids.append(v.id)
                    conn.execute(
                        """INSERT INTO vacancies
                           (id, position, company, city, province, province_code,
                            quota, registered, majors, levels, deadline,
                            is_government, payload, first_seen, last_seen)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (v.id, v.position, v.company, v.city, v.province, v.province_code,
                         v.quota, v.registered, json.dumps(v.majors, ensure_ascii=False),
                         json.dumps(v.levels, ensure_ascii=False), deadline,
                         int(v.is_government), payload, now, now),
                    )
                else:
                    if row["registered"] != v.registered or row["quota"] != v.quota:
                        changed.append({
                            "id": v.id,
                            "position": v.position,
                            "company": v.company,
                            "registered_before": row["registered"],
                            "registered_after": v.registered,
                        })
                    conn.execute(
                        """UPDATE vacancies SET position=?, company=?, city=?, province=?,
                               province_code=?, quota=?, registered=?, majors=?, levels=?,
                               deadline=?, is_government=?, payload=?, last_seen=?
                           WHERE id=?""",
                        (v.position, v.company, v.city, v.province, v.province_code,
                         v.quota, v.registered, json.dumps(v.majors, ensure_ascii=False),
                         json.dumps(v.levels, ensure_ascii=False), deadline,
                         int(v.is_government), payload, now, v.id),
                    )

                conn.execute(
                    "INSERT INTO snapshots (vacancy_id, registered, quota, captured_at) "
                    "VALUES (?,?,?,?)",
                    (v.id, v.registered, v.quota, now),
                )

        return {"new": new_ids, "changed": changed, "total": len(vacancies)}

    def record_run(self, source: str, total: int, new_count: int, started_at: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO runs (source, total, new_count, started_at, finished_at) "
                "VALUES (?,?,?,?,?)",
                (source, total, new_count, started_at, _now()),
            )

    # ------------------------------------------------------------------ #
    def all_vacancies(self) -> list[Vacancy]:
        with self.connect() as conn:
            rows = conn.execute("SELECT payload FROM vacancies").fetchall()
        out: list[Vacancy] = []
        for row in rows:
            try:
                out.append(Vacancy.from_dict(json.loads(row["payload"])))
            except (json.JSONDecodeError, TypeError):
                continue
        return out

    def get(self, vacancy_id: str) -> Vacancy | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM vacancies WHERE id = ?", (vacancy_id,)
            ).fetchone()
        if not row:
            return None
        return Vacancy.from_dict(json.loads(row["payload"]))

    def new_since(self, iso_ts: str) -> list[Vacancy]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM vacancies WHERE first_seen >= ?", (iso_ts,)
            ).fetchall()
        return [Vacancy.from_dict(json.loads(r["payload"])) for r in rows]

    def trend(self, vacancy_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT registered, quota, captured_at FROM snapshots "
                "WHERE vacancy_id = ? ORDER BY captured_at",
                (vacancy_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Application tracker
    # ------------------------------------------------------------------ #
    def track(
        self,
        vacancy_id: str,
        status: str = "shortlisted",
        score: float | None = None,
        note: str = "",
        letter_path: str = "",
    ) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Status '{status}' tidak valid. Pilih: {', '.join(VALID_STATUSES)}"
            )
        now = _now()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT vacancy_id FROM applications WHERE vacancy_id = ?", (vacancy_id,)
            ).fetchone()
            if existing:
                fields, values = ["status = ?", "updated_at = ?"], [status, now]
                if score is not None:
                    fields.append("score = ?"); values.append(score)
                if note:
                    fields.append("note = ?"); values.append(note)
                if letter_path:
                    fields.append("letter_path = ?"); values.append(letter_path)
                values.append(vacancy_id)
                conn.execute(
                    f"UPDATE applications SET {', '.join(fields)} WHERE vacancy_id = ?",
                    values,
                )
            else:
                conn.execute(
                    """INSERT INTO applications
                       (vacancy_id, status, score, note, letter_path, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (vacancy_id, status, score, note, letter_path, now, now),
                )

    def applications(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = """SELECT a.*, v.position, v.company, v.city, v.province, v.deadline
                 FROM applications a LEFT JOIN vacancies v ON v.id = a.vacancy_id"""
        params: tuple[Any, ...] = ()
        if status:
            sql += " WHERE a.status = ?"
            params = (status,)
        sql += " ORDER BY a.updated_at DESC"
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def application_status(self, vacancy_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT status FROM applications WHERE vacancy_id = ?", (vacancy_id,)
            ).fetchone()
        return row["status"] if row else None

    def stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM vacancies").fetchone()["c"]
            apps = conn.execute(
                "SELECT status, COUNT(*) c FROM applications GROUP BY status"
            ).fetchall()
            last_run = conn.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            open_count = conn.execute(
                "SELECT COUNT(*) c FROM vacancies WHERE deadline IS NULL OR deadline >= ?",
                (date.today().isoformat(),),
            ).fetchone()["c"]
        return {
            "total_vacancies": total,
            "open_vacancies": open_count,
            "applications": {r["status"]: r["c"] for r in apps},
            "last_run": dict(last_run) if last_run else None,
        }
