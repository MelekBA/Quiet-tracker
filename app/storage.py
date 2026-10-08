from .db import get_db


def export_json(user_id):
    db = get_db()

    habits = [dict(r) for r in db.execute(
        "SELECT id, name, color, created FROM habits "
        "WHERE user_id = %s ORDER BY position, id",
        (user_id,)
    ).fetchall()]

    logs = {}
    for r in db.execute(
        "SELECT l.date, l.habit_id, l.done FROM logs l "
        "JOIN habits h ON h.id = l.habit_id "
        "WHERE h.user_id = %s ORDER BY l.date, l.habit_id",
        (user_id,)
    ):
        logs.setdefault(r["date"], {})[r["habit_id"]] = bool(r["done"])

    notes = {}
    for r in db.execute(
        "SELECT n.date, n.habit_id, n.note FROM notes n "
        "JOIN habits h ON h.id = n.habit_id "
        "WHERE h.user_id = %s ORDER BY n.date, n.habit_id",
        (user_id,)
    ):
        notes.setdefault(r["date"], {})[r["habit_id"]] = r["note"]

    return {"habits": habits, "logs": logs, "notes": notes}