import os
import json
import pytest
from unittest.mock import patch, MagicMock

# --- Tests for API routes (/api/*) ---

@pytest.fixture(autouse=True)
def clear_control_caches():
    import src.routes.control
    src.routes.control._docker_installed_cache = None
    src.routes.control._docker_installed_time = 0.0
    src.routes.control._status_cache = None
    src.routes.control._status_time = 0.0
    src.routes.control._cached_tunnel_url = None
    src.routes.control._stats_cache = None
    src.routes.control._stats_time = 0.0
    import src.routes.api
    src.routes.api._url_cache = {}


def test_list_cookie_files(client, clean_user_dir):
    # Test empty list
    response = client.get("/api/cookie-files")
    assert response.status_code == 200
    assert response.json == {"files": []}

    # Test listing file that matches criteria
    cookie_file = os.path.join(clean_user_dir, "instagram_cookies.txt")
    with open(cookie_file, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        
    response = client.get("/api/cookie-files")
    assert response.status_code == 200
    assert "instagram_cookies.txt" in response.json["files"]


def test_cobalt_proxy_success(client, mock_requests_post):
    # Mock Cobalt API success response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "tunnel",
        "url": "http://cobalt-direct-url/video.mp4",
        "filename": "video.mp4"
    }
    mock_requests_post.return_value = mock_resp

    payload = {"url": "https://youtube.com/watch?v=123"}
    response = client.post("/api/cobalt", json=payload)
    assert response.status_code == 200
    assert response.json["status"] == "tunnel"
    assert response.json["url"] == "http://cobalt-direct-url/video.mp4"


def test_cobalt_proxy_fallback_to_ytdlp(client, mock_requests_post, mock_ytdlp):
    # Mock Cobalt API returning an error
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "error"}
    mock_requests_post.return_value = mock_resp

    # Mock yt_dlp extraction
    mock_instance = MagicMock()
    mock_ytdlp.return_value.__enter__.return_value = mock_instance
    mock_instance.extract_info.return_value = {
        "title": "Fallback Video",
        "url": "http://fallback-stream/video.mp4"
    }

    payload = {"url": "https://youtube.com/watch?v=123"}
    response = client.post("/api/cobalt", json=payload)
    assert response.status_code == 200
    assert response.json["status"] == "tunnel"
    assert response.json["filename"] == "Fallback Video.mp4"
    assert response.json["url"] == "http://fallback-stream/video.mp4"


def test_stream_download(client, mock_urlopen):
    # Mock remote video stream response
    mock_stream = MagicMock()
    mock_stream.read.side_effect = [b"chunk1", b"chunk2", b""]
    mock_stream.headers = {
        "Content-Type": "video/mp4",
        "Content-Length": "12"
    }
    mock_urlopen.return_value = mock_stream

    response = client.get("/api/stream?url=http://remote-url/video.mp4&filename=test.mp4")
    assert response.status_code == 302
    assert response.headers["Location"] == "http://remote-url/video.mp4"


def test_direct_download_success(client, mock_requests_post, mock_urlopen):
    # Mock Cobalt API success response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "tunnel",
        "url": "http://cobalt-direct-url/video.mp4",
        "filename": "resolved_video.mp4"
    }
    mock_requests_post.return_value = mock_resp

    # Mock remote stream reader
    mock_stream = MagicMock()
    mock_stream.read.side_effect = [b"data_chunk", b""]
    mock_stream.headers = {"Content-Type": "video/mp4"}
    mock_urlopen.return_value = mock_stream

    response = client.get("/api/download?url=https://youtube.com/watch?v=123")
    assert response.status_code == 302
    assert response.headers["Location"] == "http://cobalt-direct-url/video.mp4"

# --- Tests for Control routes (/api/control/*) ---


def test_control_action_valid(client, mock_subprocess_popen):
    payload = {"action": "start"}
    response = client.post("/api/control/action", json=payload)
    assert response.status_code == 200
    assert response.json == {"status": "initiated", "action": "start"}
    assert mock_subprocess_popen.call_count == 1


def test_control_action_invalid(client):
    payload = {"action": "invalid_action"}
    response = client.post("/api/control/action", json=payload)
    assert response.status_code == 400
    assert "Invalid action" in response.json["error"]


def test_control_status_docker_offline(client):
    # Mock docker command failure (docker not running)
    with patch("src.routes.control.run_docker_cmd") as mock_run:
        mock_run.return_value = ("", "Docker is not running", -1)
        
        response = client.get("/api/control/status")
        assert response.status_code == 200
        assert response.json["docker_installed"] is False
        assert response.json["status"] == "offline"


def test_control_status_docker_online(client):
    # Mock docker command successes
    # 1. docker info -> online
    # 2. docker compose ps -> running container info
    # 3. docker logs cloudflare-tunnel -> tunnel URL
    with patch("src.routes.control.run_docker_cmd") as mock_run:
        ps_output = json.dumps({
            "Name": "reclip-app",
            "Service": "app",
            "State": "running",
            "Publishers": None
        })
        logs_output = "https://mocked-tunnel-id.trycloudflare.com"
        
        mock_run.side_effect = [
            ("docker info details", "", 0),
            (ps_output, "", 0),
            ("", logs_output, 0)
        ]
        
        response = client.get("/api/control/status")
        assert response.status_code == 200
        assert response.json["docker_installed"] is True
        assert response.json["status"] == "online"
        assert response.json["tunnel_url"] == "https://mocked-tunnel-id.trycloudflare.com"


def test_control_stats(client):
    # Mock docker stats json output
    with patch("src.routes.control.run_docker_cmd") as mock_run:
        stats_line = json.dumps({
            "Name": "reclip-app",
            "CPUPerc": "5.50%",
            "MemPerc": "12.20%",
            "MemUsage": "100MiB / 8GiB"
        })
        mock_run.return_value = (stats_line, "", 0)
        
        response = client.get("/api/control/stats")
        assert response.status_code == 200
        assert len(response.json["containers"]) == 1
        assert response.json["containers"][0]["name"] == "reclip-app"
        assert response.json["totals"]["cpu"] == "5.5%"
        assert response.json["totals"]["memory"] == "12.2%"


def test_control_logs(client):
    with patch("src.routes.control.run_docker_cmd") as mock_run:
        mock_run.return_value = ("log_line_1\nlog_line_2", "", 0)
        
        response = client.get("/api/control/logs?service=app")
        assert response.status_code == 200
        assert response.json["logs"] == "log_line_1\nlog_line_2"


def test_cookie_status(client, clean_user_dir):
    with patch.dict(os.environ, {"YOUTUBE_COOKIES": "some_cookie"}):
        response = client.get("/api/control/cookie-status")
        assert response.status_code == 200
        assert response.json["YOUTUBE_COOKIES"] is True
        assert response.json["INSTAGRAM_COOKIES"] is False


def test_usage_stats(client):
    with patch("src.metrics.get_metrics") as mock_get_metrics:
        mock_metrics = {"total_requests": 5, "successful_requests": 4, "failed_requests": 1}
        mock_get_metrics.return_value = mock_metrics
        
        response = client.get("/api/control/usage-stats")
        assert response.status_code == 200
        assert response.json == mock_metrics


def test_save_cookie(client, clean_user_dir):
    payload = {
        "service": "youtube",
        "cookies": "key1=val1; key2=val2"
    }
    response = client.post("/api/control/cookies", json=payload)
    assert response.status_code == 200
    assert response.json["status"] == "success"
    
    # Check file exists and contents
    cookie_file = os.path.join(clean_user_dir, "youtube_cookies.txt")
    assert os.path.exists(cookie_file)
    with open(cookie_file, "r") as f:
        content = f.read()
        assert ".youtube.com" in content
        assert "key1" in content
        assert "val1" in content


def test_delete_cookie(client, clean_user_dir):
    # Save a file first
    cookie_file = os.path.join(clean_user_dir, "youtube_cookies.txt")
    with open(cookie_file, "w") as f:
        f.write("dummy")
        
    response = client.delete("/api/control/cookies/youtube")
    assert response.status_code == 200
    assert response.json["status"] == "success"
    assert not os.path.exists(cookie_file)

    # Deleting missing cookie -> 404
    response = client.delete("/api/control/cookies/youtube")
    assert response.status_code == 404
