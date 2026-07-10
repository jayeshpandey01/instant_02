import pytest
import os
import sys
from unittest.mock import MagicMock, patch

# Ensure project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set dummy environment variables for tests
os.environ["COBALT_URL"] = "http://mocked-cobalt-url/"
os.environ["USER_DIR"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "mocked_user_dir"))
os.environ["DOWNLOAD_DIR"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "mocked_downloads"))

# Create dirs if not existing
os.makedirs(os.environ["USER_DIR"], exist_ok=True)
os.makedirs(os.environ["DOWNLOAD_DIR"], exist_ok=True)

# Prevent load_env() from running at import time by patching it temporarily during app import
with patch("src.config.load_env"):
    from app import app as flask_app


@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
    })
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_requests_post():
    with patch("requests.post") as mock_post:
        yield mock_post


@pytest.fixture
def mock_requests_get():
    with patch("requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def mock_subprocess_popen():
    with patch("subprocess.Popen") as mock_popen:
        yield mock_popen


@pytest.fixture
def mock_ytdlp():
    with patch("yt_dlp.YoutubeDL") as mock_ydl:
        yield mock_ydl


@pytest.fixture
def mock_urlopen():
    with patch("urllib.request.urlopen") as mock_open:
        yield mock_open


@pytest.fixture
def clean_user_dir():
    # Helper to clean the mocked user directory between tests
    user_dir = os.environ["USER_DIR"]
    for name in os.listdir(user_dir):
        path = os.path.join(user_dir, name)
        if os.path.isfile(path):
            os.remove(path)
    yield user_dir
    for name in os.listdir(user_dir):
        path = os.path.join(user_dir, name)
        if os.path.isfile(path):
            os.remove(path)
