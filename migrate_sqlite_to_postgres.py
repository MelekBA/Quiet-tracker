"""One-time migration: app/data/tracker.db (SQLite) → Postgres.

Creates the owner account, assigns all existing rows to it, and preserves
insertion order as habits.position. Idempotent — safe to re-run.

Reads DATABASE_URL from the environment. Set MIGRATE_USERNAME / MIGRATE_PASSWORD
to control the owner credentials (defaults: owner / changeme).
"""

import os
import sqlite3
import sys
import uuid
from datetime import date
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash

load_dotenv()

BASE = Path(__file__).resolve().parent
SQLITE_PATH = BASE / "app" / "data" / "tracker.db"

DEFAULT_USERNAME = os.environ.get("MIGRATE_USERNAME", "owner")
DEFAULT_PASSWORD = os.environ.get("MIGRATE_PASSWORD", "changeme")


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_URL is not set.")
    if not SQLITE_PATH.exists():
        sys.exit(f"No SQLite file at {SQLITE_PATH} — nothing to migrate.")

    src = sqlite3.connect(SQLITE_PATH)
    src.row_factory = sqlite3.Row

    with psycopg.connect(dsn, row_factory=dict_row) as dst:
        with dst.cursor() as cur:
            # --- owner account ---
            cur.execute("SELECT id FROM users WHERE username = %s", (DEFAULT_USERNAME,))
            row = cur.fetchone()
            if row:
                user_id = row["id"]
                print(f"Reusing user '{DEFAULT_USERNAME}' ({user_id})")
            else:
                user_id = str(uuid.uuid4())[:8]
                cur.execute(
                    "INSERT INTO users (id, username, password_hash, created) "
                    "VALUES (%s, %s, %s, %s)",
                    (
                        user_id,
                        DEFAULT_USERNAME,
                        generate_password_hash(DEFAULT_PASSWORD),
                        date.today().isoformat(),
                    ),
                )
                print(f"Created user '{DEFAULT_USERNAME}' ({user_id})")

            # --- habits (rowid order becomes position) ---
            habits = src.execute(
                "SELECT id, name, color, created FROM habits ORDER BY rowid"
            ).fetchall()
            for pos, h in enumerate(habits, start=1):
                cur.execute(
                    "INSERT INTO habits (id, user_id, name, color, created, position) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "  user_id  = EXCLUDED.user_id, "
                    "  name     = EXCLUDED.name, "
                    "  color    = EXCLUDED.color, "
                    "  created  = EXCLUDED.created, "
                    "  position = EXCLUDED.position",
                    (h["id"], user_id, h["name"], h["color"], h["created"], pos),
                )
            valid_ids = {h["id"] for h in habits}

            # --- logs ---
            n_logs = skipped_logs = 0
            for r in src.execute("SELECT date, habit_id, done FROM logs"):
                if r["habit_id"] not in valid_ids:
                    skipped_logs += 1
                    continue
                cur.execute(
                    "INSERT INTO logs (date, habit_id, done) VALUES (%s, %s, %s) "
                    "ON CONFLICT (date, habit_id) DO UPDATE SET done = EXCLUDED.done",
                    (r["date"], r["habit_id"], r["done"]),
                )
                n_logs += 1

            # --- notes ---
            n_notes = skipped_notes = 0
            for r in src.execute("SELECT date, habit_id, note FROM notes"):
                if r["habit_id"] not in valid_ids:
                    skipped_notes += 1
                    continue
                cur.execute(
                    "INSERT INTO notes (date, habit_id, note) VALUES (%s, %s, %s) "
                    "ON CONFLICT (date, habit_id) DO UPDATE SET note = EXCLUDED.note",
                    (r["date"], r["habit_id"], r["note"]),
                )
                n_notes += 1

        dst.commit()

        with dst.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM habits")
            n_h = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM logs")
            n_l = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM notes")
            n_n = cur.fetchone()["n"]

    src.close()

    print("\nMigrated:")
    print(f"  habits: {len(habits)}")
    print(f"  logs:   {n_logs}  (skipped orphans: {skipped_logs})")
    print(f"  notes:  {n_notes}  (skipped orphans: {skipped_notes})")
    print(f"\nPostgres totals → habits={n_h}  logs={n_l}  notes={n_n}")


if __name__ == "__main__":
    main()
