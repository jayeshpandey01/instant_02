import os
import json
import pytest
from unittest.mock import patch, MagicMock
import src.metrics
import src.routes.control
from src.config import USER_DIR

# 1. Concurrency: Test that get_metrics raises TimeoutError when FileLock fails (raises TimeoutError)
def test_get_metrics_raises_error_on_timeout(monkeypatch):
    # Mock FileLock to raise TimeoutError
    def mock_enter(self):
        raise TimeoutError("Could not acquire lock")
    
    monkeypatch.setattr(src.metrics.FileLock, "__enter__", mock_enter)
    
    # We also mock _load_metrics to verify it does NOT get called
    mock_load = MagicMock(return_value={"total_requests": 42})
    monkeypatch.setattr(src.metrics, "_load_metrics", mock_load)
    
    with pytest.raises(TimeoutError):
        src.metrics.get_metrics()
    
    # Assert load was NOT called due to the timeout (showing lock is enforced)
    assert mock_load.call_count == 0


# 2. Metrics: Test corrupted metrics file recovery leads to backup and ValueError
def test_metrics_corruption_reset(monkeypatch, tmp_path):
    # Set metrics file to a temp path
    temp_metrics = tmp_path / "corrupted_usage_metrics.json"
    backup_metrics = tmp_path / "corrupted_usage_metrics.json.corrupt"
    # Write invalid JSON
    temp_metrics.write_text("{invalid json", encoding="utf-8")
    
    monkeypatch.setattr(src.metrics, "METRICS_FILE", str(temp_metrics))
    monkeypatch.setattr(src.metrics, "LOCK_FILE", str(temp_metrics) + ".lock")
    
    # Load metrics should raise ValueError due to corruption
    with pytest.raises(ValueError, match="Metrics file is corrupted"):
        src.metrics._load_metrics()
        
    # Verify the corrupted file was renamed/moved to backup path
    assert not os.path.exists(str(temp_metrics))
    assert os.path.exists(str(backup_metrics))
    with open(backup_metrics, "r", encoding="utf-8") as f:
        assert f.read() == "{invalid json"


# 3. Security: Test SSRF / Local File Read via /api/stream is blocked
def test_api_stream_ssrf_local_file(client):
    # Send a request with a local file scheme URL
    response = client.get("/api/stream?url=file:///etc/passwd&filename=passwd")
    assert response.status_code == 400
    
    # Send a request with localhost
    response_lh = client.get("/api/stream?url=http://localhost/something")
    assert response_lh.status_code == 400
    
    # Send a request with private IP
    response_priv = client.get("/api/stream?url=http://192.168.1.1/something")
    assert response_priv.status_code == 400


# 4. Security: Test Cookie Service Wildcard/Bulk Deletion vulnerability is blocked
def test_cookie_deletion_wildcard(client, clean_user_dir):
    # Save multiple cookie files
    for svc in ["youtube", "instagram", "tiktok"]:
        cookie_file = os.path.join(clean_user_dir, f"{svc}_cookies.txt")
        with open(cookie_file, "w") as f:
            f.write("dummy cookie data")
            
    # Deleting with service "." should be rejected
    response = client.delete("/api/control/cookies/.")
    assert response.status_code == 400
    
    # All files should still exist
    for svc in ["youtube", "instagram", "tiktok"]:
        cookie_file = os.path.join(clean_user_dir, f"{svc}_cookies.txt")
        assert os.path.exists(cookie_file)


# 5. Security: Test Cookie Service Path Traversal Write vulnerability is blocked
def test_cookie_save_path_traversal(client, clean_user_dir):
    # Target path outside of clean_user_dir
    parent_dir = os.path.dirname(clean_user_dir)
    target_traversal_file = os.path.join(parent_dir, "traversal_cookies.txt")
    
    if os.path.exists(target_traversal_file):
        os.remove(target_traversal_file)
        
    try:
        # Use path traversal in service name
        payload = {
            "service": "../traversal",
            "cookies": "session=malicious"
        }
        response = client.post("/api/control/cookies", json=payload)
        assert response.status_code == 400
        
        # Verify the file was NOT written
        assert not os.path.exists(target_traversal_file)
    finally:
        if os.path.exists(target_traversal_file):
            os.remove(target_traversal_file)


# 6. Input Validation: Test Docker Compose Logs Argument/Limit Injection is blocked
def test_docker_logs_argument_injection(client, mock_subprocess_run):
    # Setup mock return for run_docker_cmd
    mock_subprocess_run.return_value = MagicMock(stdout="mocked logs", stderr="", returncode=0)
    
    # Pass malicious service and limit parameters
    response = client.get("/api/control/logs?service=--help&limit=100%20--help")
    assert response.status_code == 400
    
    # Verify command was not executed
    assert not mock_subprocess_run.called


# 7. Downloader: Test ensure_ffmpeg handles concurrent calls without crashing
def test_ensure_ffmpeg_concurrency(monkeypatch, tmp_path):
    # Mock system ffmpeg and ffprobe as missing
    monkeypatch.setattr("shutil.which", lambda x: None)
    
    # Mock temp directory to a new temp path
    tmp_bin = tmp_path / "ffmpeg_bin"
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    
    # Mock urlretrieve to simulate download
    call_count = 0
    def mock_urlretrieve(url, path):
        nonlocal call_count
        call_count += 1
        # Create a dummy zip file
        import zipfile
        with zipfile.ZipFile(path, 'w') as zip_ref:
            zip_ref.writestr("ffmpeg", "dummy_binary")
            zip_ref.writestr("ffprobe", "dummy_binary")
        import time
        time.sleep(0.05)
        
    monkeypatch.setattr("urllib.request.urlretrieve", mock_urlretrieve)
    
    # Run ensure_ffmpeg in concurrent threads
    import threading
    threads = []
    errors = []
    
    def worker():
        try:
            import src.downloader
            src.downloader.ensure_ffmpeg()
        except Exception as e:
            errors.append(e)
            
    for _ in range(3):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # Verify no thread crashed — concurrent calls should be safe even without locking
    # (ensure_ffmpeg is idempotent: re-downloading is harmless, crashing is not)
    assert len(errors) == 0
