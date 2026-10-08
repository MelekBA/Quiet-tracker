from app import create_app
from app.db import get_db

app = create_app()
with app.app_context():
    db = get_db()
    cur = db.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )
    print([r["table_name"] for r in cur.fetchall()])