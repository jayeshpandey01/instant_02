import os
import sys
import subprocess
import json
import re
import time
from flask import Blueprint, request, jsonify
from src.config import BASE_DIR

control_bp = Blueprint("control", __name__)


def run_docker_cmd(args, timeout=15):
    """Helper to run a docker command and return stdout/stderr.
    BUG-012 FIX: Use shell=False with a list — shell=True + list only runs
    args[0] on Windows, silently dropping all other arguments.
    """
    try:
        cwd = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else BASE_DIR
        result = subprocess.run(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,          # ← BUG-012 fixed
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except Exception as e:
        return "", str(e), -1


# Cache variables
_docker_installed_cache = None
_docker_installed_time = 0.0

_status_cache = None
_status_time = 0.0
_cached_tunnel_url = None

_stats_cache = None
_stats_time = 0.0


@control_bp.route("/api/control/action", methods=["POST"])
def control_action():
    global _status_cache, _status_time, _cached_tunnel_url
    
    # Clear status cache when /api/control/action is called
    _status_cache = None
    _status_time = 0.0
    _cached_tunnel_url = None

    data = request.get_json(silent=True) or {}
    action = data.get("action")

    if action not in ["start", "stop", "restart", "rebuild"]:
        return jsonify({"error": "Invalid action"}), 400

    cmd = []
    if action == "start":
        cmd = ["docker", "compose", "-p", "reclip", "up", "-d"]
    elif action == "stop":
        cmd = ["docker", "compose", "-p", "reclip", "down"]
    elif action == "restart":
        cmd = ["docker", "compose", "-p", "reclip", "restart"]
    elif action == "rebuild":
        cmd = ["docker", "compose", "-p", "reclip", "up", "-d", "--build"]

    try:
        log_dir = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else BASE_DIR
        log_file_path = os.path.join(log_dir, "docker_compose.log")

        # BUG-014 FIX: Write the header in its own context manager first,
        # then open a SEPARATE handle for Popen to inherit.
        # The context manager would close the handle before the subprocess
        # finishes writing, corrupting/truncating logs on Windows.
        with open(log_file_path, "a", encoding="utf-8") as header_f:
            header_f.write(
                f"\n--- Running action: {action} at "
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
            )

        # Open a fresh handle — intentionally not closed so subprocess can write to it.
        # The OS reclaims this handle when the child process exits.
        log_f = open(log_file_path, "a", encoding="utf-8")  # noqa: WPS515
        cwd = os.path.dirname(sys.executable) if hasattr(sys, '_MEIPASS') else BASE_DIR
        subprocess.Popen(
            cmd,
            cwd=cwd,
            shell=False,          # ← BUG-012 fixed
            stdout=log_f,
            stderr=log_f,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )

        return jsonify({"status": "initiated", "action": action})
    except Exception as e:
        return jsonify({"error": f"Failed to launch process: {str(e)}"}), 500


@control_bp.route("/api/control/status", methods=["GET"])
def control_status():
    global _docker_installed_cache, _docker_installed_time
    global _status_cache, _status_time, _cached_tunnel_url

    now = time.time()

    # 1. Check docker_installed cache (30s cache)
    if _docker_installed_cache is not None and (now - _docker_installed_time < 30.0):
        docker_installed = _docker_installed_cache
    else:
        stdout_info, _, code_info = run_docker_cmd(["docker", "info"])
        docker_installed = (code_info == 0)
        _docker_installed_cache = docker_installed
        _docker_installed_time = now

    if not docker_installed:
        return jsonify({
            "docker_installed": False,
            "status": "offline",
            "containers": [],
            "tunnel_url": None
        })

    # 2. Check status cache (5s cache)
    if _status_cache is not None and (now - _status_time < 5.0):
        return jsonify(_status_cache)

    # Check container statuses via docker compose ps
    stdout_ps, _, code_ps = run_docker_cmd(
        ["docker", "compose", "-p", "reclip", "ps", "--format", "json"]
    )

    containers = []
    is_any_running = False

    if code_ps == 0 and stdout_ps.strip():
        try:
            lines = stdout_ps.strip().split("\n")
            for line in lines:
                if not line.strip():
                    continue
                if line.startswith("["):
                    items = json.loads(line)
                    for item in items:
                        containers.append({
                            "name": item.get("Name") or item.get("Service"),
                            "service": item.get("Service"),
                            "status": item.get("State") or item.get("Status"),
                            "ports": item.get("Publishers") or item.get("Ports")
                        })
                else:
                    item = json.loads(line)
                    containers.append({
                        "name": item.get("Name") or item.get("Service"),
                        "service": item.get("Service"),
                        "status": item.get("State") or item.get("Status"),
                        "ports": item.get("Publishers") or item.get("Ports")
                    })

            is_any_running = any(
                c.get("status") and (
                    c["status"].lower() == "running" or
                    c["status"].lower().startswith("up")
                )
                for c in containers
            )
        except Exception as err:
            print("Failed to parse docker compose ps output:", str(err))

    # Extract dynamic Cloudflare Quick Tunnel URL
    tunnel_url = _cached_tunnel_url
    if is_any_running:
        if tunnel_url is None:
            # Only query docker logs if tunnel_url is not already cached
            stdout_logs, stderr_logs, code_logs = run_docker_cmd(
                ["docker", "logs", "cloudflare-tunnel"],
                timeout=10
            )
            if code_logs == 0:
                combined = (stdout_logs or "") + (stderr_logs or "")
                matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", combined)
                if matches:
                    tunnel_url = matches[-1]
                    _cached_tunnel_url = tunnel_url

    _status_cache = {
        "docker_installed": True,
        "status": "online" if is_any_running else "offline",
        "containers": containers,
        "tunnel_url": tunnel_url
    }
    _status_time = now

    return jsonify(_status_cache)


@control_bp.route("/api/control/stats", methods=["GET"])
def control_stats():
    global _stats_cache, _stats_time
    now = time.time()

    if _stats_cache is not None and (now - _stats_time < 3.0):
        return jsonify(_stats_cache)

    stdout, _, code = run_docker_cmd(
        ["docker", "stats", "--no-stream", "--format", "json"]
    )

    stats_list = []
    total_cpu = 0.0
    total_mem = 0.0

    if code == 0 and stdout.strip():
        lines = stdout.strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                name = data.get("Name")
                cpu_str = data.get("CPUPerc", "0.00%")
                mem_str = data.get("MemPerc", "0.00%")
                mem_usage = data.get("MemUsage", "0B / 0B")

                cpu_val = float(cpu_str.replace("%", "").strip())
                mem_val = float(mem_str.replace("%", "").strip())

                total_cpu += cpu_val
                total_mem += mem_val

                stats_list.append({
                    "name": name,
                    "cpu": cpu_str,
                    "memory": mem_str,
                    "memory_usage": mem_usage
                })
            except Exception as e:
                print("Failed to parse docker stats line:", str(e))

    _stats_cache = {
        "containers": stats_list,
        "totals": {
            "cpu": f"{round(total_cpu, 1)}%",
            "memory": f"{round(total_mem, 1)}%"
        }
    }
    _stats_time = now

    return jsonify(_stats_cache)


@control_bp.route("/api/control/logs", methods=["GET"])
def control_logs():
    service = request.args.get("service")
    limit = request.args.get("limit", "100")

    if service:
        if not re.match(r"^[a-zA-Z0-9\-]+$", service):
            return jsonify({"error": "Invalid service name"}), 400

    if limit:
        if not re.match(r"^\d+$", limit):
            return jsonify({"error": "Invalid limit parameter"}), 400

    args = ["docker", "compose", "-p", "reclip", "logs", f"--tail={limit}"]
    if service:
        args.append(service)

    # BUG-016 FIX: Use 30s timeout for log fetching (was 10s — too short for large outputs)
    stdout, stderr, code = run_docker_cmd(args, timeout=30)

    if code != 0:
        return jsonify({"logs": f"Error loading logs: {stderr}"}), 500

    return jsonify({"logs": stdout or "No logs available."})


# BUG-006 FIX: Real cookie status endpoint — checks actual env vars and files
@control_bp.route("/api/control/cookie-status", methods=["GET"])
def cookie_status():
    """Returns which cookie env-vars or text files are actually configured."""
    services = ["YOUTUBE", "INSTAGRAM", "TWITTER", "TIKTOK"]
    result = {}
    from src.config import USER_DIR
    
    for svc in services:
        key = f"{svc}_COOKIES"
        is_set = bool(os.environ.get(key))
        if not is_set:
            # Check for file matching the service domain
            try:
                for name in os.listdir(USER_DIR):
                    if name.endswith(".txt") and svc.lower() in name.lower():
                        is_set = True
                        break
            except Exception:
                pass
        result[key] = is_set
    return jsonify(result)


@control_bp.route("/api/control/usage-stats", methods=["GET"])
def usage_stats():
    from src.metrics import get_metrics
    return jsonify(get_metrics())


@control_bp.route("/api/control/cookies", methods=["POST"])
def save_cookie():
    data = request.get_json(silent=True) or {}
    service = data.get("service")
    cookies_text = data.get("cookies", "").strip()
    
    if not service or not cookies_text:
        return jsonify({"error": "Missing service or cookies"}), 400
        
    if ".." in service or "/" in service or "\\" in service:
        return jsonify({"error": "Path traversal detected"}), 400
        
    service_clean = service.lower().replace("_cookies", "")
    if not service_clean or not re.match(r"^[a-zA-Z0-9]+$", service_clean):
        return jsonify({"error": "Invalid service name"}), 400
        
    service = service_clean
    
    import time
    # Clean leading 'Cookie: ' or 'cookie: ' header labels
    if re.match(r"^cookie:\s*", cookies_text, re.IGNORECASE):
        cookies_text = re.sub(r"^cookie:\s*", "", cookies_text, flags=re.IGNORECASE).strip()

    if cookies_text.startswith("# Netscape") or "\t" in cookies_text:
        # Validate Netscape format has at least one valid line with 7 tab-separated columns
        valid_lines = 0
        for line in cookies_text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            parts = line_str.split("\t")
            if len(parts) >= 7:
                valid_lines += 1
        
        if valid_lines == 0:
            return jsonify({"error": "Invalid Netscape cookies format. It must contain at least one row with 7 tab-separated columns."}), 400
            
        netscape_text = cookies_text
    else:
        # Convert raw header to Netscape
        domain_map = {
            "youtube": ".youtube.com",
            "instagram": ".instagram.com",
            "twitter": ".twitter.com",
            "x": ".x.com",
            "tiktok": ".tiktok.com"
        }
        domain = domain_map.get(service, f".{service}.com")
        
        lines = [
            "# Netscape HTTP Cookie File",
            "# Generated by Reclip Control from raw header",
            ""
        ]
        valid_pairs = 0
        for part in cookies_text.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            key, val = part.split("=", 1)
            key = key.strip()
            val = val.strip()
            # Clean and filter out malformed cookie key/value pairs
            if key and val:
                if any(c in key for c in " \r\n\t"):
                    continue
                expire = int(time.time() + 31536000)
                lines.append(f"{domain}\tTRUE\t/\tTRUE\t{expire}\t{key}\t{val}")
                valid_pairs += 1
                
        if valid_pairs == 0:
            return jsonify({"error": "No valid cookies detected. Please paste a valid Netscape cookie file or a standard HTTP 'Cookie' header."}), 400
            
        netscape_text = "\n".join(lines)
        
    from src.config import USER_DIR
    file_path = os.path.join(USER_DIR, f"{service}_cookies.txt")
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(netscape_text)
        return jsonify({"status": "success", "message": f"Saved {service} cookies"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@control_bp.route("/api/control/cookies/<service>", methods=["DELETE"])
def delete_cookie(service):
    from src.config import USER_DIR
    if ".." in service or "/" in service or "\\" in service:
        return jsonify({"error": "Path traversal detected"}), 400
        
    service_clean = service.lower().replace("_cookies", "")
    if not service_clean or not re.match(r"^[a-zA-Z0-9]+$", service_clean):
        return jsonify({"error": "Invalid service name"}), 400
        
    service = service_clean
    
    deleted = False
    try:
        for name in os.listdir(USER_DIR):
            if name.endswith(".txt") and service in name.lower():
                file_path = os.path.join(USER_DIR, name)
                os.remove(file_path)
                deleted = True
                
        if deleted:
            return jsonify({"status": "success", "message": f"Deleted {service} cookies"})
        else:
            return jsonify({"status": "not_found", "message": "No cookies found to delete"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
