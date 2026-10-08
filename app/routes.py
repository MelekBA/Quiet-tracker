import io
import json
from datetime import date, timedelta

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from . import auth, models
from .storage import export_json

main = Blueprint("main", __name__)

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _streaks(done_dates, today):
    """done_dates is a set of ISO strings. Returns (current, best)."""
    if not done_dates:
        return 0, 0
    cur = 0
    d = today
    while d.isoformat() in done_dates:
        cur += 1
        d -= timedelta(days=1)
    ordered = sorted(date.fromisoformat(x) for x in done_dates)
    best = run = 1
    for i in range(1, len(ordered)):
        if (ordered[i] - ordered[i - 1]).days == 1:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return cur, best


# ---------- auth ----------

@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = auth.verify_password(username, password)
        if user:
            login_user(user)
            return redirect(url_for("main.home"))
        error = "Wrong username or password."
    return render_template("login.html", error=error)


@main.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            error = "Username and password are required."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif auth.get_user_by_username(username):
            error = "That username is taken."
        else:
            user = auth.create_user(username, password)
            login_user(user)
            return redirect(url_for("main.home"))
    return render_template("register.html", error=error)


@main.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


# ---------- dashboard ----------

@main.route("/")
@login_required
def home():
    today = date.today()
    today_str = today.isoformat()

    days = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        days.append({
            "iso": d.isoformat(),
            "label": WEEKDAYS[d.weekday()],
            "day_num": d.day,
            "is_today": d == today,
            "weekday": d.weekday(),
        })

    uid = current_user.id
    habits = models.get_habits(uid)
    all_logs = models.get_all_logs(uid)
    today_notes = models.get_notes_for_date(uid, today_str)

    done_by_habit = {}
    for r in all_logs:
        if r["done"]:
            done_by_habit.setdefault(r["habit_id"], set()).add(r["date"])

    monday_this_week = today - timedelta(days=today.weekday())
    heatmap_start = monday_this_week - timedelta(weeks=11)
    heatmap_days = [heatmap_start + timedelta(days=i) for i in range(84)]

    habits_with_state = []
    for habit in habits:
        done = done_by_habit.get(habit["id"], set())
        current_streak, best_streak = _streaks(done, today)
        habits_with_state.append({
            **habit,
            "done_today": today_str in done,
            "streak": current_streak,
            "best": best_streak,
            "days": {d["iso"]: (d["iso"] in done) for d in days},
            "heatmap": [
                {
                    "iso": d.isoformat(),
                    "done": d.isoformat() in done,
                    "future": d > today,
                    "is_today": d == today,
                }
                for d in heatmap_days
            ],
            "note": today_notes.get(habit["id"], ""),
            "has_data": bool(done),
            "milestone": current_streak in (7, 30, 100, 365),
        })

    for day in days:
        day["count"] = sum(1 for h in habits_with_state if h["days"][day["iso"]])
        day["total"] = len(habits_with_state)

    today_done = sum(1 for h in habits_with_state if h["done_today"])
    today_total = len(habits_with_state)
    today_pct = round(today_done / today_total * 100) if today_total else 0
    longest_streak = max((h["streak"] for h in habits_with_state), default=0)

    return render_template(
        "index.html",
        today=today_str, days=days, habits=habits_with_state,
        today_done=today_done, today_total=today_total,
        today_pct=today_pct, longest_streak=longest_streak,
    )


# ---------- habit actions ----------

@main.route("/add", methods=["POST"])
@login_required
def add():
    name = request.form.get("name", "").strip()
    color = request.form.get("color", "#7c9a92")
    if name:
        models.add_habit(current_user.id, name, color)
    return redirect(url_for("main.home"))


@main.route("/toggle/<date_str>/<habit_id>", methods=["POST"])
@login_required
def toggle(date_str, habit_id):
    result = models.toggle_habit(current_user.id, date_str, habit_id)
    if result is None:
        abort(404)
    return redirect(url_for("main.home"))


@main.route("/delete/<habit_id>", methods=["POST"])
@login_required
def delete(habit_id):
    if not models.delete_habit(current_user.id, habit_id):
        abort(404)
    return redirect(url_for("main.home"))


@main.route("/note/<date_str>/<habit_id>", methods=["POST"])
@login_required
def note(date_str, habit_id):
    text = request.form.get("note", "")
    if not models.set_note(current_user.id, date_str, habit_id, text):
        abort(404)
    return redirect(url_for("main.home"))


# ---------- data endpoints ----------

@main.route("/export")
@login_required
def export():
    filename = f"quiet-tracker-{date.today().isoformat()}.json"
    payload = json.dumps(
        export_json(current_user.id), indent=2, ensure_ascii=False
    ).encode("utf-8")
    return send_file(
        io.BytesIO(payload),
        as_attachment=True,
        download_name=filename,
        mimetype="application/json",
    )


@main.route("/stats")
@login_required
def stats():
    return jsonify(models.get_completion_stats(current_user.id, window_days=30))


@main.route("/stats/daily")
@login_required
def stats_daily():
    return jsonify(models.get_daily_totals(current_user.id, window_days=30))


@main.route("/compare")
@login_required
def compare():
    period = request.args.get("period", "week")
    if period not in ("week", "month", "year"):
        period = "week"
    return render_template(
        "compare.html", data=models.get_comparison(current_user.id, period)
    )


@main.route("/compare/data")
@login_required
def compare_data():
    period = request.args.get("period", "week")
    if period not in ("week", "month", "year"):
        period = "week"
    return jsonify(models.get_comparison(current_user.id, period))  