import os
import threading
from flask import Flask
from src.config import load_env
from src.database import init_db
from src.tasks import cleanup_loop

# Initialize environment
load_env()

# Ensure FFmpeg is available
from src.downloader import ensure_ffmpeg
ensure_ffmpeg()

# Initialize Flask app
app = Flask(__name__)

# Register Blueprints
from src.routes.views import views_bp
from src.routes.blog import blog_bp
from src.routes.api import api_bp

app.register_blueprint(views_bp)
app.register_blueprint(blog_bp)
app.register_blueprint(api_bp)

# Initialize database
init_db()

# Start background cleanup thread
cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8899))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=True, exclude_patterns=["**/downloads/*", "downloads/*", "**/downloads", "*.db", "*.db-journal", "*.txt"])
