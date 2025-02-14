from flask import Flask, session
from datetime import timedelta


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = "@#Ts3Plus2025B3ll4Cruz$%"
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

    @app.before_request
    def make_session_permanent():
        session.permanent = True

    # Importar y registrar rutas
    from .routes import init_routes
    init_routes(app)

    return app
