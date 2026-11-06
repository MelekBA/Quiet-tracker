import io
import requests
import os
import json
from datetime import date, timedelta
from pywebpush import webpush, WebPushException
from flask import current_app, jsonify
from openai import OpenAI
from .db import get_db

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
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
    all_habits = models.get_habits(uid)
    daily_habits = [h for h in all_habits if not h["period"]]
    flexible_habits = [h for h in all_habits if h["period"]]
    
    period_counts = models.get_period_counts(uid)
    for h in flexible_habits:
        h["period_count"] = period_counts.get(h["id"], 0)

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
    for habit in daily_habits:
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
    today_total = len(habits_with_state) # Only daily habits count towards the percentage
    today_pct = round(today_done / today_total * 100) if today_total else 0
    longest_streak = max((h["streak"] for h in habits_with_state), default=0)

    return render_template(
        "index.html",
        today=today_str, days=days, habits=habits_with_state, flexible_habits=flexible_habits,
        today_done=today_done, today_total=today_total,
        today_pct=today_pct, longest_streak=longest_streak,
    )


# ---------- habit actions ----------

@main.route("/add", methods=["POST"])
@login_required
def add():
    name = request.form.get("name", "").strip()
    color = request.form.get("color", "#7c9a92")
    period = request.form.get("period", "")
    if period not in ("week", "month"):
        period = None
    if name:
        models.add_habit(current_user.id, name, color, period)
    return redirect(url_for("main.home"))


@main.route("/toggle/<date_str>/<habit_id>", methods=["POST"])
@login_required
def toggle(date_str, habit_id):
    result = models.toggle_habit(current_user.id, date_str, habit_id)
    if result is None:
        abort(404)
    return redirect(url_for("main.home"))
@main.route("/flexible/increment/<habit_id>", methods=["POST"])
@login_required
def increment_flexible(habit_id):
    result = models.increment_flexible(current_user.id, date.today().isoformat(), habit_id)
    if result is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"count": result})


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

@main.route("/sw.js")
def service_worker():
    response = send_from_directory(current_app.static_folder, "sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response
@main.route("/settings")
@login_required
def settings():
    return render_template("settings.html")
@main.route("/settings/save_reminder", methods=["POST"])
@login_required
def save_reminder():
    time_str = request.form.get("reminder_time")
    if time_str:
        models.update_reminder_time(current_user.id, time_str)
    return redirect(url_for("main.settings"))

@main.route("/push/public_key")
def push_public_key():
    return jsonify({"publicKey": current_app.config["VAPID_PUBLIC_KEY"]})

@main.route("/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    sub_info = request.json
    if not sub_info:
        return jsonify({"error": "No subscription data"}), 400
    models.save_subscription(current_user.id, sub_info)
    return jsonify({"status": "success"})

@main.route("/cron/notifications")
def cron_notifications():
    from datetime import datetime
    import zoneinfo
    from .db import get_db
    db = get_db()

    tunisia_tz = zoneinfo.ZoneInfo("Africa/Tunis")
    now = datetime.now(tunisia_tz)
    today_str = now.strftime("%Y-%m-%d")

    # Fetch users who have a reminder time and haven't been notified today
    users = db.execute(
        "SELECT u.id, u.reminder_time, s.endpoint, s.p256dh, s.auth "
        "FROM users u JOIN push_subscriptions s ON u.id = s.user_id "
        "WHERE u.reminder_time IS NOT NULL AND (u.last_notified_date IS NULL OR u.last_notified_date != %s)",
        (today_str,)
    ).fetchall()

    success_count = 0

    for user in users:
        rem_time = user['reminder_time']
        rem_h, rem_m = map(int, rem_time.split(':'))
        
        # If the current time is PAST the reminder time (and we haven't sent it today)
        if now.hour > rem_h or (now.hour == rem_h and now.minute >= rem_m):
            sub_info = {
                "endpoint": user["endpoint"],
                "keys": {"p256dh": user["p256dh"], "auth": user["auth"]}
            }
            try:
                webpush(
                    subscription_info=sub_info,
                    data=json.dumps({
                        "title": "Quiet Tracker",
                        "body": "Time for your daily habits! Keep your streak alive."
                    }),
                    vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
                    vapid_claims={"sub": current_app.config["VAPID_CLAIM_EMAIL"]}
                )
                success_count += 1
                # Mark as notified for today so they don't get spammed
                db.execute("UPDATE users SET last_notified_date = %s WHERE id = %s", (today_str, user['id']))
            except WebPushException as ex:
                if ex.response and ex.response.status_code == 410:
                    models.delete_subscription(user["endpoint"])
                print(f"Push failed: {ex}")

    db.commit()
    return jsonify({"status": "done", "sent": success_count})
@main.route("/cron/test_notification")
def test_notification():
    from pywebpush import webpush, WebPushException
    from .db import get_db
    import json
    db = get_db()
    # Fetch ALL subscriptions, ignoring the reminder time
    rows = db.execute("SELECT endpoint, p256dh, auth FROM push_subscriptions").fetchall()
    if not rows:
        return "No subscriptions found in the database!"
    
    success = 0
    errors = []
    for r in rows:
        sub_info = {
            "endpoint": r["endpoint"],
            "keys": {"p256dh": r["p256dh"], "auth": r["auth"]}
        }
        try:
            webpush(
                subscription_info=sub_info,
                data=json.dumps({"title": "Test Alert!", "body": "If you see this, push works!"}),
                vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
                vapid_claims={"sub": current_app.config["VAPID_CLAIM_EMAIL"]}
            )
            success += 1
        except Exception as ex:
            errors.append(str(ex))
            print(f"Error: {ex}")
            
    if errors:
        return f"Sent {success} successfully. Errors: {errors}"
    return f"Successfully sent {success} notifications!"

@main.route("/settings/save_profile", methods=["POST"])
@login_required
def save_profile():
    new_username = request.form.get("username", "").strip()
    new_bio = request.form.get("bio", "").strip()
    new_avatar = request.form.get("avatar_base64") # Hidden input from JS
    
    # Basic validation
    if not new_username or len(new_username) < 3:
        return redirect(url_for("main.settings")) # Add flash message later if desired
        
    db = get_db()
    
    # Check if the new username is taken by someone else
    if new_username != current_user.username:
        existing = db.execute("SELECT id FROM users WHERE username = %s", (new_username,)).fetchone()
        if existing:
            return redirect(url_for("main.settings")) # Username taken
    
    # Update the database
    db.execute(
        "UPDATE users SET username = %s, bio = %s, avatar = %s WHERE id = %s",
        (new_username, new_bio, new_avatar if new_avatar else current_user.avatar, current_user.id)
    )
    db.commit()
    
    return redirect(url_for("main.settings"))

@main.route("/api/ask", methods=["POST"])
@login_required
def api_ask():
    data = request.json
    question = data.get("question")
    if not question:
        return jsonify({"error": "No question provided"}), 400

    # 1. Fetch ALL user data from the database
    uid = current_user.id
    habits = models.get_habits(uid)
    
    # Get daily stats (ignores flexible habits)
    daily_stats = models.get_completion_stats(uid, window_days=30)
    
    # Get flexible habit counts (this week/this month)
    flex_counts = models.get_period_counts(uid)

    # 2. Format the data for the AI
    daily_habits_data = []
    flexible_habits_data = []
    
    for h in habits:
        if h["period"]:
            flexible_habits_data.append({
                "name": h["name"],
                "period": h["period"],
                "count_this_period": flex_counts.get(h["id"], 0)
            })
        else:
            daily_habits_data.append({"name": h["name"]})

    # 3. Build the JSON context
    context = {
        "user_profile": {
            "name": current_user.username,
            "bio": current_user.bio or "No bio provided yet."
        },
        "daily_habits": daily_habits_data,
        "flexible_habits": flexible_habits_data, # Now the AI sees these!
        "stats_30d": daily_stats,
    }
    context_json = json.dumps(context, ensure_ascii=False)

        # 4. Build the messages
    system_prompt = f"""
    You are a helpful, concise habit coach inside an app called Quiet Tracker.
    
    Here is the user's profile and habit data in JSON format:
    {context_json}
    
    Answer the user directly in a friendly tone based on the data provided. Keep it under 3 sentences. 
    
    Remember that 'flexible_habits' are counted by week or month, not daily.
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    # 5. Send to Groq
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return jsonify({"error": "GROQ_API_KEY is not set on the server."}), 500

    try:
        client = OpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.3,
            max_tokens=400
        )
        
        ai_reply = response.choices[0].message.content
        return jsonify({"answer": ai_reply.strip()})

    except Exception as e:
        print(f"AI API Error: {e}")
        return jsonify({"error": "The AI service is currently unavailable."}), 500