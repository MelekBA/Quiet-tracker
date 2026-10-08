
import psycopg
from flask import current_app, g
from psycopg.rows import dict_row

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS habits (
    id       TEXT PRIMARY KEY,
    user_id  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name     TEXT NOT NULL,
    color    TEXT NOT NULL,
    created  TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS logs (
    date     TEXT NOT NULL,
    habit_id TEXT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    done     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, habit_id)
);

CREATE TABLE IF NOT EXISTS notes (
    date     TEXT NOT NULL,
    habit_id TEXT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    note     TEXT NOT NULL,
    PRIMARY KEY (date, habit_id)
);

CREATE INDEX IF NOT EXISTS idx_habits_user ON habits(user_id, position);
CREATE INDEX IF NOT EXISTS idx_logs_habit  ON logs(habit_id, done);
"""


def get_db():
    if "db" not in g:
        g.db = psycopg.connect(
            current_app.config["DATABASE_URL"],
            row_factory=dict_row,
        )
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(SCHEMA)
        db.commit()
        
        
        