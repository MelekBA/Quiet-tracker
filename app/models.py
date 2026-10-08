import uuid
from datetime import date, timedelta

from .db import get_db


def get_habits(user_id):
    rows = get_db().execute(
        "SELECT id, name, color, created FROM habits "
        "WHERE user_id = %s ORDER BY position, id",
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def add_habit(user_id, name, color="#7c9a92"):
    hid = str(uuid.uuid4())[:8]
    created = date.today().isoformat()
    db = get_db()
    row = db.execute(
        "SELECT COALESCE(MAX(position), 0) AS p FROM habits WHERE user_id = %s",
        (user_id,)
    ).fetchone()
    db.execute(
        "INSERT INTO habits (id, user_id, name, color, created, position) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (hid, user_id, name, color, created, row["p"] + 1),
    )
    db.commit()
    return {"id": hid, "name": name, "color": color, "created": created}


def _owned(db, habit_id, user_id):
    return db.execute(
        "SELECT 1 FROM habits WHERE id = %s AND user_id = %s",
        (habit_id, user_id)
    ).fetchone() is not None


def delete_habit(user_id, habit_id):
    db = get_db()
    if not _owned(db, habit_id, user_id):
        return False
    db.execute("DELETE FROM habits WHERE id = %s", (habit_id,))
    db.commit()
    return True


def toggle_habit(user_id, date_str, habit_id):
    db = get_db()
    if not _owned(db, habit_id, user_id):
        return None
    row = db.execute(
        "SELECT done FROM logs WHERE date = %s AND habit_id = %s",
        (date_str, habit_id),
    ).fetchone()
    new = 0 if (row and row["done"]) else 1
    db.execute(
        "INSERT INTO logs (date, habit_id, done) VALUES (%s, %s, %s) "
        "ON CONFLICT (date, habit_id) DO UPDATE SET done = EXCLUDED.done",
        (date_str, habit_id, new),
    )
    db.commit()
    return bool(new)


def set_note(user_id, date_str, habit_id, text):
    db = get_db()
    if not _owned(db, habit_id, user_id):
        return False
    text = text.strip()
    if text:
        db.execute(
            "INSERT INTO notes (date, habit_id, note) VALUES (%s, %s, %s) "
            "ON CONFLICT (date, habit_id) DO UPDATE SET note = EXCLUDED.note",
            (date_str, habit_id, text),
        )
    else:
        db.execute(
            "DELETE FROM notes WHERE date = %s AND habit_id = %s",
            (date_str, habit_id),
        )
    db.commit()
    return True


def get_all_logs(user_id):
    rows = get_db().execute(
        "SELECT l.date, l.habit_id, l.done FROM logs l "
        "JOIN habits h ON h.id = l.habit_id "
        "WHERE h.user_id = %s",
        (user_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_notes_for_date(user_id, date_str):
    rows = get_db().execute(
        "SELECT n.habit_id, n.note FROM notes n "
        "JOIN habits h ON h.id = n.habit_id "
        "WHERE h.user_id = %s AND n.date = %s",
        (user_id, date_str)
    ).fetchall()
    return {r["habit_id"]: r["note"] for r in rows}


def get_completion_stats(user_id, window_days=30):
    db = get_db()
    today = date.today()
    start = today - timedelta(days=window_days - 1)
    done_rows = db.execute(
        "SELECT l.habit_id, COUNT(*) AS n FROM logs l "
        "JOIN habits h ON h.id = l.habit_id "
        "WHERE h.user_id = %s AND l.done = 1 AND l.date BETWEEN %s AND %s "
        "GROUP BY l.habit_id",
        (user_id, start.isoformat(), today.isoformat())
    ).fetchall()
    done_by = {r["habit_id"]: r["n"] for r in done_rows}
    habits = db.execute(
        "SELECT id, name, color, created FROM habits "
        "WHERE user_id = %s ORDER BY position, id",
        (user_id,)
    ).fetchall()
    result = []
    for h in habits:
        done = done_by.get(h["id"], 0)
        rate = round(done / window_days * 100) if window_days else 0
        created = date.fromisoformat(h["created"])
        days_old = (today - created).days + 1
        result.append({
            "id": h["id"], "name": h["name"], "color": h["color"],
            "rate": rate, "done": done, "window": window_days,
            "days_old": days_old,
        })
    return result


def get_daily_totals(user_id, window_days=30):
    db = get_db()
    today = date.today()
    start = today - timedelta(days=window_days - 1)
    done_rows = db.execute(
        "SELECT l.date, COUNT(*) AS n FROM logs l "
        "JOIN habits h ON h.id = l.habit_id "
        "WHERE h.user_id = %s AND l.done = 1 AND l.date BETWEEN %s AND %s "
        "GROUP BY l.date",
        (user_id, start.isoformat(), today.isoformat())
    ).fetchall()
    done_by = {r["date"]: r["n"] for r in done_rows}
    total = db.execute(
        "SELECT COUNT(*) AS n FROM habits WHERE user_id = %s", (user_id,)
    ).fetchone()["n"]
    result = []
    for i in range(window_days - 1, -1, -1):
        d = today - timedelta(days=i)
        key = d.isoformat()
        result.append({
            "date": key, "label": d.strftime("%b %d"),
            "done": done_by.get(key, 0), "total": total,
        })
    return result


def get_comparison(user_id, period="week"):
    db = get_db()
    today = date.today()
    spans = {"week": 7, "month": 30, "year": 365}
    days = spans.get(period, 7)
    current_start = today - timedelta(days=days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)

    def counts(start, end):
        rows = db.execute(
            "SELECT l.habit_id, COUNT(*) AS n FROM logs l "
            "JOIN habits h ON h.id = l.habit_id "
            "WHERE h.user_id = %s AND l.done = 1 AND l.date BETWEEN %s AND %s "
            "GROUP BY l.habit_id",
            (user_id, start.isoformat(), end.isoformat())
        ).fetchall()
        return {r["habit_id"]: r["n"] for r in rows}

    cur_by = counts(current_start, today)
    prev_by = counts(previous_start, previous_end)
    habits = db.execute(
        "SELECT id, name, color FROM habits WHERE user_id = %s ORDER BY position, id",
        (user_id,)
    ).fetchall()

    rows = []
    for h in habits:
        cur = cur_by.get(h["id"], 0)
        prev = prev_by.get(h["id"], 0)
        rows.append({
            "id": h["id"], "name": h["name"], "color": h["color"],
            "current": cur, "previous": prev, "delta": cur - prev,
            "days": days,
        })
    return {
        "period": period, "days": days,
        "current_range": f"{current_start.isoformat()} → {today.isoformat()}",
        "previous_range": f"{previous_start.isoformat()} → {previous_end.isoformat()}",
        "rows": rows,
    }