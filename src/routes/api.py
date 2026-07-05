import os
from flask import Blueprint, request, jsonify, send_file, after_this_request
from src.config import DOWNLOAD_DIR, BASE_DIR
from src.auth import generate_auth_token
from src.downloader import run_ytdlp_with_fallback, detect_media_type
from src.tasks import jobs, run_download
import threading
import uuid
import shutil
import glob
import re
import time

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")
    
    admin_email = os.environ.get("ADMIN_EMAIL", "Instantreelsdownload@gmail.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "@Instantreelsdownload9267")
    
    if email == admin_email and password == admin_password:
        token = generate_auth_token(email)
        return jsonify({"token": token, "email": email})
    
    return jsonify({"error": "Invalid email or password"}), 401

@api_bp.route("/api/cookie-files")
def list_cookie_files():
    files = []
    root_dir = os.path.dirname(__file__)
    try:
        for name in os.listdir(root_dir):
            if name.endswith(".txt") and os.path.isfile(os.path.join(root_dir, name)):
                file_path = os.path.join(root_dir, name)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        first_line = f.readline()
                        if "netscape" in first_line.lower() or "cookie" in first_line.lower() or "instagram.com" in name:
                            files.append(name)
                except Exception:
                    pass
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"files": files})

@api_bp.route("/api/diagnose")
def diagnose_env():
    import sys
    import shutil
    import subprocess
    
    ffmpeg_sys = shutil.which("ffmpeg")
    ffprobe_sys = shutil.which("ffprobe")
    ffmpeg_custom = os.path.exists("/tmp/bin/ffmpeg")
    
    version = "unknown"
    if ffmpeg_sys:
        try:
            version = subprocess.check_output([ffmpeg_sys, "-version"], text=True).split("\n")[0]
        except Exception as e:
            version = f"error: {e}"
            
    return jsonify({
        "platform": sys.platform,
        "ffmpeg_in_path": ffmpeg_sys,
        "ffprobe_in_path": ffprobe_sys,
        "ffmpeg_in_tmp": ffmpeg_custom,
        "ffmpeg_version": version,
        "env_path": os.environ.get("PATH", ""),
        "environ": {k: v for k, v in os.environ.items() if "SECRET" not in k and "PASSWORD" not in k and "KEY" not in k}
    })

@api_bp.route("/api/info", methods=["POST"])
def get_info():
    data = request.json
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    cookies_data = data.get("cookies")
    ydl_opts_base = {
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "ignore_no_formats_error": True,
    }
    try:
        info, used_cookie, fallback, err = run_ytdlp_with_fallback(ydl_opts_base, url, cookies_data, download=False)
        if err:
            return jsonify({"error": err.split("\n")[-1]}), 400

        # Check if extracted info represents a playlist or carousel
        is_carousel = False
        item_count = 0
        formats = []
        
        if info.get("_type") == "playlist" or "entries" in info:
            is_carousel = True
            entries = info.get("entries", [])
            item_count = len(entries)
            
            first_entry = entries[0] if entries else {}
            title = info.get("title") or first_entry.get("title") or "Gallery Post"
            thumbnail = info.get("thumbnail") or first_entry.get("thumbnail") or ""
            uploader = info.get("uploader") or first_entry.get("uploader") or ""
            duration = info.get("duration") or first_entry.get("duration")
        else:
            title = info.get("title", "")
            thumbnail = info.get("thumbnail", "")
            uploader = info.get("uploader", "")
            duration = info.get("duration")
            
            # Build quality options — prefer progressive (video+audio) formats per resolution
            best_by_height = {}
            for f in info.get("formats", []):
                height = f.get("height")
                vcodec = f.get("vcodec", "none").lower()
                acodec = f.get("acodec", "none").lower()
                if height and vcodec != "none":
                    tbr = f.get("tbr") or 0
                    is_h264 = "avc" in vcodec or "h264" in vcodec
                    has_audio = acodec != "none"

                    if height not in best_by_height:
                        best_by_height[height] = f
                    else:
                        existing = best_by_height[height]
                        existing_vcodec = existing.get("vcodec", "none").lower()
                        existing_is_h264 = "avc" in existing_vcodec or "h264" in existing_vcodec
                        existing_has_audio = existing.get("acodec", "none").lower() != "none"

                        if has_audio and not existing_has_audio:
                            best_by_height[height] = f
                        elif has_audio == existing_has_audio:
                            if is_h264 and not existing_is_h264:
                                best_by_height[height] = f
                            elif is_h264 == existing_is_h264:
                                if tbr > (existing.get("tbr") or 0):
                                    best_by_height[height] = f

            for height, f in best_by_height.items():
                formats.append({
                    "id": f["format_id"],
                    "label": f"{height}p",
                    "height": height,
                })
            formats.sort(key=lambda x: x["height"], reverse=True)

        media_type = detect_media_type(info)

        res_data = {
            "title": title,
            "media_type": media_type,
            "thumbnail": thumbnail,
            "duration": duration,
            "uploader": uploader,
            "formats": formats,
            "is_carousel": is_carousel,
            "item_count": item_count,
        }
        if fallback:
            res_data["fallback_used"] = used_cookie
        return jsonify(res_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@api_bp.route("/api/playlist-info", methods=["POST"])
def get_playlist_info():
    data = request.json
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    cookies_data = data.get("cookies")
    ydl_opts_base = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "no_warnings": True,
    }
    try:
        info, used_cookie, fallback, err = run_ytdlp_with_fallback(ydl_opts_base, url, cookies_data, download=False)
        if err:
            return jsonify({"error": err.split("\n")[-1]}), 400

        entries = info.get("entries", [])
        urls = [entry.get("url") for entry in entries if entry.get("url")]
        res_data = {"urls": urls}
        if fallback:
            res_data["fallback_used"] = used_cookie
        return jsonify(res_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@api_bp.route("/api/download", methods=["POST"])
def start_download():
    data = request.json
    url = data.get("url", "").strip()
    format_choice = data.get("format", "video")
    format_id = data.get("format_id")
    title = data.get("title", "")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    cookies_data = data.get("cookies")

    job_id = uuid.uuid4().hex[:10]
    jobs[job_id] = {"status": "downloading", "url": url, "title": title, "created_at": time.time()}

    thread = threading.Thread(
        target=run_download,
        args=(job_id, url, format_choice, format_id, cookies_data)
    )
    thread.daemon = True
    thread.start()

    return jsonify({"job_id": job_id})

@api_bp.route("/api/status/<job_id>")
def check_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": job["status"],
        "error": job.get("error"),
        "filename": job.get("filename"),
        "fallback_used": job.get("fallback_used"),
        "progress": job.get("progress", 0),
    })

@api_bp.route("/api/file/<job_id>")
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404

    file_path = job["file"]
    filename = job["filename"]

    # Determine the correct MIME type for iOS compatibility
    _, ext = os.path.splitext(filename)
    if ext.lower() in [".mp4", ".m4v", ".mov"]:
        mimetype = "video/mp4"
    elif ext.lower() == ".mp3":
        mimetype = "audio/mpeg"
    elif ext.lower() == ".zip":
        mimetype = "application/zip"
    else:
        mimetype = None

    response = send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        conditional=True,     # Enables HTTP 206 Partial Content + Range request support (required by iOS Safari)
        mimetype=mimetype,
    )
    response.headers["Accept-Ranges"] = "bytes"
    return response

@api_bp.route("/api/cleanup", methods=["POST"])
def cleanup_jobs():
    data = request.json or {}
    job_ids = data.get("job_ids", [])
    cleaned = []
    for job_id in job_ids:
        job = jobs.pop(job_id, None)
        if job and "file" in job:
            file_path = job["file"]
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                cleaned.append(job_id)
            except Exception:
                pass
    return jsonify({"status": "success", "cleaned": cleaned})

