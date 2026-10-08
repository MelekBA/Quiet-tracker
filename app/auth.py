import uuid
from datetime import date

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


def get_user(user_id):
    row = get_db().execute(
        "SELECT id, username FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    return User(row["id"], row["username"]) if row else None


def get_user_by_username(username):
    row = get_db().execute(
        "SELECT id, username FROM users WHERE username = %s", (username,)
    ).fetchone()
    return User(row["id"], row["username"]) if row else None


def create_user(username, password):
    uid = str(uuid.uuid4())[:8]
    db = get_db()
    db.execute(
        "INSERT INTO users (id, username, password_hash, created) "
        "VALUES (%s, %s, %s, %s)",
        (uid, username, generate_password_hash(password), date.today().isoformat()),
    )
    db.commit()
    return User(uid, username)


def verify_password(username, password):
    row = get_db().execute(
        "SELECT id, username, password_hash FROM users WHERE username = %s",
        (username,),
    ).fetchone()
    if not row:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return User(row["id"], row["username"])