import os
import json
import threading
import time
from src.config import BASE_DIR

METRICS_FILE = os.path.join(BASE_DIR, "usage_metrics.json")
LOCK_FILE = METRICS_FILE + ".lock"
_lock = threading.Lock()


class FileLock:
    def __init__(self, lock_file, timeout=5.0, delay=0.05):
        self.lock_file = lock_file
        self.timeout = timeout
        self.delay = delay
        self.fd = None

    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                self.fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except (FileExistsError, OSError):
                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Could not acquire lock on {self.lock_file} within {self.timeout}s")
                time.sleep(self.delay)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                os.remove(self.lock_file)
            except OSError:
                pass


def _load_metrics():
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            backup_file = METRICS_FILE + ".corrupt"
            try:
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(METRICS_FILE, backup_file)
                print(f"Corrupted metrics file backed up to {backup_file}")
            except Exception as rename_err:
                print(f"Failed to rename corrupted metrics file: {rename_err}")
            raise ValueError(f"Metrics file is corrupted: {e}")
    return {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "platforms": {
            "youtube": 0,
            "instagram": 0,
            "twitter": 0,
            "tiktok": 0,
            "other": 0
        }
    }


def _save_metrics(data):
    temp_file = METRICS_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(temp_file, METRICS_FILE)
    except Exception as e:
        print(f"Failed to save metrics: {e}")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass


def get_platform_from_url(url):
    url = (url or "").lower()
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "instagram.com" in url:
        return "instagram"
    elif "twitter.com" in url or "x.com" in url:
        return "twitter"
    elif "tiktok.com" in url:
        return "tiktok"
    return "other"


def track_request(url=None, success=True):
    try:
        with _lock:
            with FileLock(LOCK_FILE):
                data = _load_metrics()
                
                data["total_requests"] += 1
                if success:
                    data["successful_requests"] += 1
                    if url:
                        platform = get_platform_from_url(url)
                        if platform not in data["platforms"]:
                            data["platforms"][platform] = 0
                        data["platforms"][platform] += 1
                else:
                    data["failed_requests"] += 1
                    
                _save_metrics(data)
    except Exception as e:
        print(f"Failed to track request: {e}")


def get_metrics():
    with _lock:
        with FileLock(LOCK_FILE):
            return _load_metrics()
