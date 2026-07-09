import os
import sys

if os.environ.get("DOWNLOAD_DIR"):
    DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR")
elif os.environ.get("VERCEL"):
    DOWNLOAD_DIR = "/tmp/downloads"
else:
    base_path = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else os.path.dirname(os.path.dirname(__file__))
    DOWNLOAD_DIR = os.path.join(base_path, "downloads")

if os.environ.get("USER_DIR"):
    USER_DIR = os.environ.get("USER_DIR")
elif hasattr(sys, '_MEIPASS'):
    USER_DIR = os.path.dirname(sys.executable)
else:
    USER_DIR = os.path.dirname(os.path.dirname(__file__))

if hasattr(sys, '_MEIPASS'):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.dirname(__file__))

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def load_env():
    if hasattr(sys, '_MEIPASS'):
        env_path = os.path.join(os.path.dirname(sys.executable), ".env")
    else:
        env_path = os.path.join(BASE_DIR, ".env")

    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            in_double = False
            in_single = False
            escaped = False
            comment_idx = -1
            for i, char in enumerate(line):
                if escaped:
                    escaped = False
                    continue
                if char == '\\':
                    escaped = True
                    continue
                if char == '"' and not in_single:
                    in_double = not in_double
                elif char == "'" and not in_double:
                    in_single = not in_single
                elif char == '#' and not in_double and not in_single:
                    comment_idx = i
                    break
            if comment_idx != -1:
                line = line[:comment_idx].strip()

            if "=" not in line:
                continue

            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'").strip('"')

            if key:
                os.environ[key] = val
