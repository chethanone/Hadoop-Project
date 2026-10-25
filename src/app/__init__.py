"""
Flask Application Factory.
Initializes the Flask app, registers blueprints, and sets up template helpers.
"""

from flask import Flask, render_template

from .config import Config, config_by_name
from .routes import diagnostics_bp, file_manager_bp, mapreduce_bp, dashboard_bp


def format_bytes(size: int) -> str:
    """Format bytes into human-readable representation."""
    if not isinstance(size, (int, float)) or size < 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def create_app(config_name: str = "default") -> Flask:
    """Creates and configures an instance of the Flask application."""
    # Cache same-origin CSS/JS for a day; versioned assets are refreshed by
    # the browser when the URL changes. This avoids revalidating on each page.
    app = Flask(__name__)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400

    # Load configuration
    if isinstance(config_name, str):
        config_class = config_by_name.get(config_name, Config)
        app.config.from_object(config_class)
    else:
        app.config.from_object(config_name)

    # Store config instance for service layers
    app.config["HADOOP_CONFIG_INSTANCE"] = config_class() if isinstance(config_class, type) else config_class

    # Register template filters
    app.jinja_env.filters["format_bytes"] = format_bytes

    # Register blueprints
    app.register_blueprint(diagnostics_bp)
    app.register_blueprint(file_manager_bp)
    app.register_blueprint(mapreduce_bp)
    app.register_blueprint(dashboard_bp)

    # Global error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template(
            "diagnostics.html",
            error_message="Resource not found (404)"
        ), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template(
            "diagnostics.html",
            error_message="Internal server error occurred (500)"
        ), 500

    return app
