import os
import sys
import socket
import shutil
import subprocess
import threading
import time

from app import app
from src.config import BASE_DIR


# -----------------------------------------------------------------------------
# BUG-047 FIX: When running as a bundled .exe, sys._MEIPASS is a RANDOM temp
# directory that changes every launch. docker-compose.yml in _MEIPASS means
# Docker Compose loses track of the project between restarts.
# Solution: copy runtime files to a stable directory next to the .exe on first run.
# -----------------------------------------------------------------------------
def ensure_stable_runtime_files():
    """Copy docker-compose.yml and the cobalt build directory from the bundle to the stable .exe directory."""
    if not hasattr(sys, '_MEIPASS'):
        return  # Development mode - files are already in the project root

    stable_dir = os.path.dirname(sys.executable)
    
    # 1. Copy docker-compose.yml
    src_compose = os.path.join(sys._MEIPASS, 'docker-compose.yml')
    dst_compose = os.path.join(stable_dir, 'docker-compose.yml')
    if os.path.exists(src_compose) and not os.path.exists(dst_compose):
        try:
            shutil.copy2(src_compose, dst_compose)
            print(f"Copied docker-compose.yml -> {dst_compose}")
        except Exception as e:
            print(f"Warning: could not copy docker-compose.yml: {e}")

    # 2. Copy cobalt directory (recursively)
    src_cobalt = os.path.join(sys._MEIPASS, 'cobalt')
    dst_cobalt = os.path.join(stable_dir, 'cobalt')
    if os.path.exists(src_cobalt) and not os.path.exists(dst_cobalt):
        try:
            shutil.copytree(src_cobalt, dst_cobalt)
            print(f"Copied cobalt/ directory -> {dst_cobalt}")
        except Exception as e:
            print(f"Warning: could not copy cobalt directory: {e}")


def wait_for_server(host='127.0.0.1', port=8899, timeout=15):
    """
    BUG-040 FIX: Poll until Flask is actually accepting connections.
    Replaces the blind time.sleep(1) which races on slow machines.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False

_flask_port = None

def show_native_error(title, message):
    """
    Used when pywebview is unavailable or when a fatal startup error occurs.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()  # Hide the empty root window
        root.attributes('-topmost', True)  # Bring dialog to front
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        # Last resort: just print to stderr if tkinter is somehow unavailable
        print(f"ERROR — {title}: {message}", file=sys.stderr)


def show_error_and_exit(title, message):
    """Display a native error dialog and exit. Never opens an external browser."""
    webview = get_webview()
    if webview is None:
        # pywebview unavailable — use native tkinter dialog instead of opening browser
        show_native_error(title, message)
        sys.exit(1)

    webview.create_window(
        title=title,
        html=(
            "<body style='background:#0A0B0E;color:#fff;font-family:sans-serif;"
            "padding:40px;text-align:center;'>"
            f"<h2>{title}</h2><p>{message}</p>"
            "<button onclick='window.close()' "
            "style='margin-top:20px;padding:10px 20px;background:#E11D48;"
            "color:white;border:none;border-radius:4px;cursor:pointer;'>Exit</button>"
            "</body>"
        ),
        width=500,
        height=300,
        resizable=False
    )
    webview.start()
    sys.exit(1)


def start_flask(preferred_port=8899):
    global _flask_port
    for port in [preferred_port, preferred_port + 1, preferred_port + 2]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            _flask_port = port
            print(f"Starting Flask on port {port}...")
            app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
            return
        except OSError as e:
            print(f"Port {port} unavailable ({e}), trying next...")
            try:
                s.close()
            except Exception:
                pass

    # All ports failed
    print("ERROR: Could not bind Flask to any available port.")
    _flask_port = -1


def on_window_closing():
    """
    BUG-042 FIX: Gracefully shut down Docker containers when the window closes.
    Without this, containers (cobalt-api, cloudflare-tunnel) kept running
    in the background, blocking ports on next launch.
    """
    print("Application closing - sending docker compose down...")
    try:
        cwd = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else BASE_DIR
        proc = subprocess.Popen(
            ["docker", "compose", "-p", "reclip", "down"],
            cwd=cwd,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            print("Docker compose down timed out after 15 seconds.")
    except Exception as e:
        print(f"Failed to stop containers on close: {e}")


def main():
    # BUG-047: Ensure runtime files are in a stable location next to the .exe
    ensure_stable_runtime_files()

    preferred_port = 8899

    # 1. Start Flask in a daemon thread
    flask_thread = threading.Thread(
        target=start_flask,
        args=(preferred_port,),
        daemon=True
    )
    flask_thread.start()

    # 2. Wait for the Flask thread to choose a port or fail
    start_time = time.time()
    while _flask_port is None and time.time() - start_time < 10:
        time.sleep(0.05)

    if _flask_port is None or _flask_port == -1:
        print("ERROR: Flask server did not bind to any available port.")
        show_native_error(
            "Reclip Control Center - Port Error",
            "Could not start the local server. Ports 8899-8901 are already in use. "
            "Please close other applications using these ports and try again."
        )
        sys.exit(1)

    active_port = _flask_port
    print(f"Waiting for Flask server to be ready on port {active_port}...")
    server_ready = wait_for_server('127.0.0.1', active_port, timeout=15)

    if not server_ready:
        print(f"ERROR: Flask server did not become ready in time on port {active_port}.")
        show_native_error(
            "Reclip Control Center - Connection Error",
            f"The local server on port {active_port} did not respond in time."
        )
        sys.exit(1)

    # 3. Open in default web browser
    url = f"http://127.0.0.1:{active_port}"
    print(f"Opening Reclip Control Center in default browser: {url}")
    import webbrowser
    webbrowser.open(url)
    
    # 4. Keep running until user presses Ctrl+C or closes the console window
    print("Reclip Control is running in the background.")
    print("Close this console window to stop the server and docker containers.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping Reclip Control...")
    finally:
        on_window_closing()


if __name__ == "__main__":
    main()