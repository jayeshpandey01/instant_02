import os
import uuid
import glob
import json
import tempfile
import threading
import time
import sqlite3
import hmac
import hashlib
import base64
from urllib.parse import urlparse
from flask import Flask, request, jsonify, send_file, render_template, after_this_request
import yt_dlp

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip("'").strip('"')
                    os.environ[key.strip()] = val

load_env()

app = Flask(__name__)

# SQLite Database Helper Functions
def get_db_connection():
    db_path = os.environ.get("DATABASE_PATH", "blog.db")
    if not os.path.isabs(db_path):
        if os.environ.get("VERCEL"):
            db_path = os.path.join("/tmp", db_path)
        else:
            db_path = os.path.join(os.path.dirname(__file__), db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            date TEXT,
            excerpt TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM blogs")
    if cursor.fetchone()[0] == 0:
        default_posts = [
            {
                "slug": "how-reclip-makes-downloads-easy",
                "title": "How Reclip Makes Downloads Effortless",
                "category": "Product",
                "date": "June 25, 2026",
                "excerpt": "A closer look at the small design choices that make every download feel calm, clear, and fast.",
                "content": json.dumps([
                    "Reclip was built to turn a complicated download flow into something that feels almost effortless. Instead of scattering options across several steps, the experience stays focused on one simple goal: getting your file ready without friction.",
                    "The secret is in the flow. You paste a link, choose a format, and the rest of the work happens smoothly in the background. That keeps the experience calm for first-time users and familiar for people who come back often.",
                    "Small details matter here too. Clear status feedback, polished buttons, and thoughtful copy all help create a sense of confidence while the download is being prepared."
                ])
            },
            {
                "slug": "why-creators-love-simple-media-tools",
                "title": "Why Creators Love Simple Media Tools",
                "category": "Creator Tips",
                "date": "June 20, 2026",
                "excerpt": "Creators often need quick access to media, and a simple workflow can save time and energy.",
                "content": json.dumps([
                    "When creators work across different platforms, speed matters. They often need to save a clip, grab an audio file, or revisit a piece of media quickly without losing momentum.",
                    "That is where simple tools shine. A polished experience helps creators keep moving instead of getting stuck in a maze of menus, redirects, or confusing steps.",
                    "Reclip focuses on that exact balance: minimal friction, clear choices, and a smooth finish so the work stays creative rather than technical."
                ])
            },
            {
                "slug": "best-practices-for-video-and-audio-downloads",
                "title": "Best Practices for Video and Audio Downloads",
                "category": "How-To",
                "date": "June 15, 2026",
                "excerpt": "A practical checklist for choosing the right format and quality before you hit download.",
                "content": json.dumps([
                    "Choosing between video and audio often depends on the purpose of the file. If you need a quick preview, a lower-quality option may be enough. If you want a more polished result, higher-quality settings are a better fit.",
                    "Audio-only downloads are ideal for podcasts, playlists, or content that will be reused in editing workflows. Video downloads are better when visual detail matters most.",
                    "The best approach is to match the format to the use case and keep the download experience simple enough that the choice feels easy instead of overwhelming."
                ])
            }
        ]
        for post in default_posts:
            cursor.execute(
                "INSERT INTO blogs (slug, title, category, date, excerpt, content) VALUES (?, ?, ?, ?, ?, ?)",
                (post["slug"], post["title"], post["category"], post["date"], post["excerpt"], post["content"])
            )
        conn.commit()
    conn.close()

init_db()

# Cryptographically Secure Admin Auth Session Token Generator & Validator
def generate_auth_token(email):
    expiry = int(time.time()) + (7 * 24 * 3600)  # 7 days
    payload = f"{email}:{expiry}"
    secret = os.environ.get("JWT_SECRET", "super_secret_key_clauster_blog").encode()
    signature = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    token_str = f"{payload}:{signature}"
    return base64.b64encode(token_str.encode()).decode()

def verify_auth_token(token):
    if not token:
        return False
    try:
        decoded = base64.b64decode(token.encode()).decode()
        parts = decoded.split(":")
        if len(parts) != 3:
            return False
        email, expiry, signature = parts
        if int(expiry) < time.time():
            return False
        payload = f"{email}:{expiry}"
        secret = os.environ.get("JWT_SECRET", "super_secret_key_clauster_blog").encode()
        expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected):
            admin_email = os.environ.get("ADMIN_EMAIL", "Instantreelsdownload@gmail.com")
            return email == admin_email
    except Exception:
        return False
    return False

DOWNLOAD_DIR = "/tmp/downloads" if os.environ.get("VERCEL") else os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


jobs = {}

def cleanup_loop():
    while True:
        time.sleep(60)
        try:
            now = time.time()
            # Clean up jobs memory dict and physical files
            for job_id, job in list(jobs.items()):
                created_at = job.get("created_at", 0)
                if created_at and (now - created_at) > 900:  # 15 minutes
                    jobs.pop(job_id, None)
                    if "file" in job:
                        try:
                            if os.path.exists(job["file"]):
                                os.remove(job["file"])
                        except Exception:
                            pass
            
            # Also clean up any older files in DOWNLOAD_DIR
            if os.path.exists(DOWNLOAD_DIR):
                for filename in os.listdir(DOWNLOAD_DIR):
                    filepath = os.path.join(DOWNLOAD_DIR, filename)
                    try:
                        if os.path.isfile(filepath):
                            mtime = os.path.getmtime(filepath)
                            if (now - mtime) > 900:  # 15 minutes
                                os.remove(filepath)
                    except Exception:
                        pass
        except Exception:
            pass

t_cleanup = threading.Thread(target=cleanup_loop, daemon=True)
t_cleanup.start()




def get_cookie_opts(cookies_data, url=None):
    """
    Returns a tuple of (opts_dict, temp_file_path).
    If a temporary file is created, its path is returned so it can be cleaned up later.
    """
    if not cookies_data:
        return {}, None
    
    mode = cookies_data.get("mode", "none")
    if mode == "browser":
        browser = cookies_data.get("browser", "").lower().strip()
        if browser:
            return {"cookiesfrombrowser": (browser,)}, None
    elif mode == "local_file":
        filename = cookies_data.get("filename", "").strip()
        if filename:
            safe_name = os.path.basename(filename)
            file_path = os.path.join(os.path.dirname(__file__), safe_name)
            if os.path.exists(file_path):
                if os.environ.get("VERCEL"):
                    # Copy to writeable /tmp to prevent Vercel read-only filesystem write errors
                    import shutil
                    tmp_path = os.path.join("/tmp", safe_name)
                    try:
                        shutil.copy2(file_path, tmp_path)
                        return {"cookiefile": tmp_path}, tmp_path
                    except Exception:
                        pass
                return {"cookiefile": file_path}, None
            else:
                raise FileNotFoundError(f"Local cookie file {safe_name} not found")
    elif mode == "text":
        cookie_text = cookies_data.get("text", "").strip()
        if cookie_text:
            if cookie_text.startswith("# Netscape") or "\t" in cookie_text:
                netscape_text = cookie_text
            else:
                # Convert raw Cookie header to Netscape format scoped to the URL's domain
                domain = ".instagram.com"
                if url:
                    try:
                        parsed = urlparse(url)
                        netloc = parsed.netloc.split(":")[0]
                        parts = netloc.split(".")
                        if len(parts) >= 2:
                            domain = "." + ".".join(parts[-2:])
                        else:
                            domain = "." + netloc
                    except Exception:
                        pass
                
                lines = [
                    "# Netscape HTTP Cookie File",
                    "# Generated by Instant Download from raw header",
                    ""
                ]
                for part in cookie_text.split(";"):
                    part = part.strip()
                    if not part or "=" not in part:
                        continue
                    key, val = part.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key and val:
                        expire = int(time.time() + 31536000)
                        lines.append(f"{domain}\tTRUE\t/\tTRUE\t{expire}\t{key}\t{val}")
                netscape_text = "\n".join(lines)

            fd, path = tempfile.mkstemp(suffix=".txt", prefix="cookies_")
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(netscape_text)
                return {"cookiefile": path}, path
            except Exception as e:
                try:
                    os.remove(path)
                except OSError:
                    pass
                raise e
    return {}, None


def find_matching_cookie_file(url):
    if not url:
        return None
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        parts = netloc.split(".")
        if len(parts) >= 2:
            base_domain = ".".join(parts[-2:])
        else:
            base_domain = netloc
        
        domain_name = base_domain.replace("www.", "").split(".")[0]
        
        root_dir = os.path.dirname(__file__)
        for name in os.listdir(root_dir):
            if name.endswith(".txt") and os.path.isfile(os.path.join(root_dir, name)):
                if domain_name in name.lower():
                    file_path = os.path.join(root_dir, name)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            first_line = f.readline()
                            if "netscape" in first_line.lower() or "cookie" in first_line.lower():
                                return file_path
                    except Exception:
                        pass
    except Exception:
        pass
    return None


def run_ytdlp_with_fallback(ydl_opts_base, url, cookies_data, download=False):
    """
    Runs a native yt-dlp operation. If mode is "none" and it fails indicating auth needed,
    it attempts to match a local cookie file and retries.
    Returns (info_dict_or_none, used_cookie_file, fallback_activated, error_msg_or_none)
    """
    mode = cookies_data.get("mode", "none") if cookies_data else "none"
    cookie_opts, temp_cookie_file = get_cookie_opts(cookies_data, url)
    
    ydl_opts = {**ydl_opts_base, **cookie_opts}
    
    fallback_activated = False
    used_cookie_file = temp_cookie_file
    
    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=download)
                return info, os.path.basename(used_cookie_file) if used_cookie_file else None, False, None
        except Exception as e:
            error_msg = str(e)
            
            needs_auth = (
                "sign in" in error_msg.lower() or
                "login" in error_msg.lower() or
                "empty media response" in error_msg.lower() or
                "confirm you are not a bot" in error_msg.lower() or
                "private video" in error_msg.lower() or
                "http error 403" in error_msg.lower() or
                "members-only" in error_msg.lower()
            )
            
            if mode == "none" and needs_auth:
                local_cookie_path = find_matching_cookie_file(url)
                if local_cookie_path:
                    fallback_activated = True
                    used_cookie_file = local_cookie_path
                    
                    cookie_path_to_use = local_cookie_path
                    temp_cleanup_path = None
                    if os.environ.get("VERCEL"):
                        import shutil
                        temp_cleanup_path = os.path.join("/tmp", os.path.basename(local_cookie_path))
                        try:
                            shutil.copy2(local_cookie_path, temp_cleanup_path)
                            cookie_path_to_use = temp_cleanup_path
                        except Exception:
                            pass
                    
                    ydl_opts_retry = {**ydl_opts_base, "cookiefile": cookie_path_to_use}
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts_retry) as ydl_retry:
                            info_retry = ydl_retry.extract_info(url, download=download)
                            # Keep temp file registered for cleanup if we created it
                            return info_retry, os.path.basename(local_cookie_path), True, None
                    except Exception as e_retry:
                        return None, os.path.basename(local_cookie_path), True, str(e_retry)
                    finally:
                        if temp_cleanup_path:
                            try:
                                os.remove(temp_cleanup_path)
                            except OSError:
                                pass
            return None, os.path.basename(used_cookie_file) if used_cookie_file else None, False, error_msg
    finally:
        if temp_cookie_file:
            try:
                os.remove(temp_cookie_file)
            except OSError:
                pass


def run_download(job_id, url, format_choice, format_id, cookies_data=None):
    try:
        job = jobs[job_id]
        # Append playlist index to support multi-item downloads without overwriting
        out_template = os.path.join(DOWNLOAD_DIR, f"{job_id}_%(playlist_index)s.%(ext)s")

        def progress_hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    job["progress"] = int(downloaded / total * 100)
                else:
                    percent_str = d.get("_percent_str")
                    if percent_str:
                        try:
                            import re
                            clean_percent = re.sub(r'\x1b\[[0-9;]*m', '', percent_str).replace("%", "").strip()
                            job["progress"] = int(float(clean_percent))
                        except Exception:
                            pass
            elif d.get("status") == "finished":
                job["progress"] = 100

        ydl_opts_base = {
            "noplaylist": False,
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "ignore_no_formats_error": True,
            "progress_hooks": [progress_hook],
        }

        import shutil
        has_ffmpeg = shutil.which("ffmpeg") is not None

        if format_choice == "audio":
            ydl_opts_base["format"] = "bestaudio/best"
            if has_ffmpeg:
                ydl_opts_base["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
        elif format_id:
            if has_ffmpeg:
                ydl_opts_base["format"] = f"{format_id}+bestaudio[acodec^=mp4a]/bestaudio/best"
                ydl_opts_base["merge_output_format"] = "mp4"
                ydl_opts_base["recode_video"] = "mp4"
            else:
                ydl_opts_base["format"] = format_id
        else:
            if has_ffmpeg:
                ydl_opts_base["format"] = "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/best[ext=mp4]/best"
                ydl_opts_base["merge_output_format"] = "mp4"
                ydl_opts_base["recode_video"] = "mp4"
            else:
                ydl_opts_base["format"] = "best[ext=mp4]/best"

        info, used_cookie, fallback, err = run_ytdlp_with_fallback(ydl_opts_base, url, cookies_data, download=True)

        if err:
            job["status"] = "error"
            job["error"] = err.split("\n")[-1]
            return

        if fallback:
            job["fallback_used"] = used_cookie

        # Find all files starting with job_id
        files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{job_id}*"))
        if not files:
            job["status"] = "error"
            job["error"] = "Download completed but no file was found"
            return

        # If multiple files are downloaded, zip them
        if len(files) > 1:
            import zipfile
            zip_filename = f"{job_id}.zip"
            zip_path = os.path.join(DOWNLOAD_DIR, zip_filename)
            
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for idx, f in enumerate(sorted(files)):
                        base = os.path.basename(f)
                        _, f_ext = os.path.splitext(base)
                        friendly_name = f"Item_{idx+1}{f_ext}"
                        zip_file.write(f, friendly_name)
                
                # Clean up individual unzipped files
                for f in files:
                    try:
                        os.remove(f)
                    except OSError:
                        pass
                
                chosen = zip_path
                ext = ".zip"
            except Exception as zip_err:
                job["status"] = "error"
                job["error"] = f"Failed to bundle zip package: {str(zip_err)}"
                return
        else:
            # Single file download
            chosen = files[0]
            ext = os.path.splitext(chosen)[1]

        job["status"] = "done"
        job["file"] = chosen
        
        # Determine title from first entry if it was a playlist/carousel
        title = ""
        if info:
            if info.get("_type") == "playlist" or "entries" in info:
                entries = info.get("entries", [])
                if entries:
                    title = info.get("title") or entries[0].get("title")
            else:
                title = info.get("title")
        
        if not title:
            title = job.get("title", "").strip()

        if title:
            safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip()[:20].strip()
            job["filename"] = f"{safe_title}{ext}" if safe_title else os.path.basename(chosen)
        else:
            job["filename"] = os.path.basename(chosen)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/")
@app.route("/download-instagram-private-reels")
@app.route("/instagram-audio-downloader")
@app.route("/download-instagram-stories")
@app.route("/instagram-video-downloader")
@app.route("/instagram-photo-downloader")
@app.route("/profile-picture-downloader")
@app.route("/about")
@app.route("/contact")
@app.route("/blog")
@app.route("/blog/<path:slug>")
@app.route("/admin")
def index(slug=None):
    return render_template("index.html")

# Admin Login API
@app.route("/api/auth/login", methods=["POST"])
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

# Get All Blogs API
@app.route("/api/blogs", methods=["GET"])
def get_blogs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blogs ORDER BY id DESC")
        rows = cursor.fetchall()
        blogs = []
        for row in rows:
            blogs.append({
                "id": row["id"],
                "slug": row["slug"],
                "title": row["title"],
                "category": row["category"],
                "date": row["date"],
                "excerpt": row["excerpt"],
                "content": json.loads(row["content"]) if row["content"] else []
            })
        conn.close()
        return jsonify(blogs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get Single Blog by Slug API
@app.route("/api/blogs/<slug>", methods=["GET"])
def get_blog_single(slug):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blogs WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return jsonify({
                "id": row["id"],
                "slug": row["slug"],
                "title": row["title"],
                "category": row["category"],
                "date": row["date"],
                "excerpt": row["excerpt"],
                "content": json.loads(row["content"]) if row["content"] else []
            })
        return jsonify({"error": "Blog post not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Create Blog API (Admin Only)
@app.route("/api/blogs", methods=["POST"])
def create_blog():
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not verify_auth_token(token):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    title = data.get("title")
    slug = data.get("slug")
    category = data.get("category", "General")
    date = data.get("date") or time.strftime("%B %d, %Y")
    content = data.get("content")
    
    if not title or not slug or not content:
        return jsonify({"error": "Title, slug, and content are required"}), 400
        
    excerpt = data.get("excerpt") or (content[0][:150] + "..." if content else "")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO blogs (slug, title, category, date, excerpt, content) VALUES (?, ?, ?, ?, ?, ?)",
            (slug, title, category, date, excerpt, json.dumps(content))
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return jsonify({"id": new_id, "slug": slug, "title": title}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "A blog post with this slug already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Update Blog API (Admin Only)
@app.route("/api/blogs/<int:blog_id>", methods=["PUT"])
def update_blog(blog_id):
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not verify_auth_token(token):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    title = data.get("title")
    slug = data.get("slug")
    category = data.get("category", "General")
    date = data.get("date") or time.strftime("%B %d, %Y")
    content = data.get("content")
    
    if not title or not slug or not content:
        return jsonify({"error": "Title, slug, and content are required"}), 400
        
    excerpt = data.get("excerpt") or (content[0][:150] + "..." if content else "")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE blogs SET slug = ?, title = ?, category = ?, date = ?, excerpt = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (slug, title, category, date, excerpt, json.dumps(content), blog_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Blog post updated successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "A blog post with this slug already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Delete Blog API (Admin Only)
@app.route("/api/blogs/<int:blog_id>", methods=["DELETE"])
def delete_blog(blog_id):
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not verify_auth_token(token):
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blogs WHERE id = ?", (blog_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Blog post deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/cookie-files")
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


@app.route("/api/info", methods=["POST"])
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
            
            # Build quality options — keep best format per resolution
            best_by_height = {}
            for f in info.get("formats", []):
                height = f.get("height")
                if height and f.get("vcodec", "none") != "none":
                    tbr = f.get("tbr") or 0
                    if height not in best_by_height or tbr > (best_by_height[height].get("tbr") or 0):
                        best_by_height[height] = f

            for height, f in best_by_height.items():
                formats.append({
                    "id": f["format_id"],
                    "label": f"{height}p",
                    "height": height,
                })
            formats.sort(key=lambda x: x["height"], reverse=True)

        res_data = {
            "title": title,
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


@app.route("/api/playlist", methods=["POST"])
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


@app.route("/api/download", methods=["POST"])
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


@app.route("/api/status/<job_id>")
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


@app.route("/api/file/<job_id>")
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "File not ready"}), 404
    
    file_path = job["file"]
    return send_file(file_path, as_attachment=True, download_name=job["filename"])


@app.route("/api/cleanup", methods=["POST"])
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



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8899))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port)
