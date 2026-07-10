import os
import json
import tempfile
import threading
import pytest
import src.metrics


@pytest.fixture
def temp_metrics_file():
    # Setup temporary file path for metrics testing
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    
    # Save original METRICS_FILE path and replace it with temp path
    orig_file = src.metrics.METRICS_FILE
    orig_lock = getattr(src.metrics, "LOCK_FILE", None)
    src.metrics.METRICS_FILE = path
    src.metrics.LOCK_FILE = path + ".lock"
    
    # Ensure starting with no file
    if os.path.exists(path):
        os.remove(path)
        
    yield path
    
    # Cleanup and restore
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    if os.path.exists(path + ".lock"):
        try:
            os.remove(path + ".lock")
        except OSError:
            pass
    src.metrics.METRICS_FILE = orig_file
    if orig_lock is not None:
        src.metrics.LOCK_FILE = orig_lock


def test_get_platform_from_url():
    assert src.metrics.get_platform_from_url("https://www.youtube.com/watch?v=123") == "youtube"
    assert src.metrics.get_platform_from_url("https://youtu.be/123") == "youtube"
    assert src.metrics.get_platform_from_url("https://instagram.com/reel/123") == "instagram"
    assert src.metrics.get_platform_from_url("https://twitter.com/user/status/123") == "twitter"
    assert src.metrics.get_platform_from_url("https://x.com/user/status/123") == "twitter"
    assert src.metrics.get_platform_from_url("https://tiktok.com/@user/video/123") == "tiktok"
    assert src.metrics.get_platform_from_url("https://other-site.com/video") == "other"
    assert src.metrics.get_platform_from_url(None) == "other"


def test_track_request_success_and_failure(temp_metrics_file):
    # Retrieve initial empty metrics structure
    metrics = src.metrics.get_metrics()
    assert metrics["total_requests"] == 0
    assert metrics["successful_requests"] == 0
    assert metrics["failed_requests"] == 0

    # Track a successful Youtube request
    src.metrics.track_request("https://youtube.com/watch?v=abc", success=True)
    # Track a failed Instagram request
    src.metrics.track_request("https://instagram.com/p/abc", success=False)
    # Track a successful request with no URL
    src.metrics.track_request(None, success=True)

    metrics = src.metrics.get_metrics()
    assert metrics["total_requests"] == 3
    assert metrics["successful_requests"] == 2
    assert metrics["failed_requests"] == 1
    assert metrics["platforms"]["youtube"] == 1
    assert metrics["platforms"]["instagram"] == 0  # Failed platform tracking remains 0


def test_metrics_concurrent_writes(temp_metrics_file):
    # Verify thread safety of metrics writing logic
    num_threads = 10
    requests_per_thread = 25
    
    threads = []
    
    def worker():
        for _ in range(requests_per_thread):
            # 1 success on YouTube
            src.metrics.track_request("https://youtube.com/watch?v=xyz", success=True)
            # 1 success on Instagram
            src.metrics.track_request("https://instagram.com/p/xyz", success=True)
            # 1 failure on Twitter
            src.metrics.track_request("https://twitter.com/status/xyz", success=False)
            
    # Spawn threads
    for _ in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
        
    # Join threads
    for t in threads:
        t.join()
        
    metrics = src.metrics.get_metrics()
    
    # Assert total and platform counts align with number of runs
    expected_total = num_threads * requests_per_thread * 3
    expected_success = num_threads * requests_per_thread * 2
    expected_failed = num_threads * requests_per_thread
    
    assert metrics["total_requests"] == expected_total
    assert metrics["successful_requests"] == expected_success
    assert metrics["failed_requests"] == expected_failed
    assert metrics["platforms"]["youtube"] == num_threads * requests_per_thread
    assert metrics["platforms"]["instagram"] == num_threads * requests_per_thread
    assert metrics["platforms"]["twitter"] == 0  # Failed requests do not increment platform counts
