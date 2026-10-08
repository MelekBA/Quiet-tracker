import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

load_dotenv()

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["DATABASE_URL"] = os.environ["DATABASE_URL"]

    from . import db
    from .auth import get_user
    from .routes import main

    db.init_db(app)
    app.teardown_appcontext(db.close_db)

    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message = ""

    @login_manager.user_loader
    def load_user(user_id):
        return get_user(user_id)

    csrf.init_app(app)
    app.register_blueprint(main)

    return app