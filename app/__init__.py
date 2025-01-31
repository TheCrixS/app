from flask import Flask


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = "supersecretkey"

    # Importar y registrar rutas
    from .routes import init_routes
    init_routes(app)

    return app
