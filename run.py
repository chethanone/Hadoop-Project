"""
Application entry point for the Hadoop File Management and MapReduce Visualization System.
"""

import os
from src.app import create_app

env_name = os.getenv("FLASK_ENV", "development")
app = create_app(env_name)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "127.0.0.1")
    print(f" * Starting Hadoop Management System on http://{host}:{port}")
    app.run(host=host, port=port, debug=app.config.get("DEBUG", True))
