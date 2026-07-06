import os
from flask import Blueprint, request, jsonify
from src.config import BASE_DIR
from src.auth import generate_auth_token
import requests

api_bp = Blueprint("api", __name__)

@api_bp.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
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
    try:
        for name in os.listdir(BASE_DIR):
            if name.endswith(".txt") and os.path.isfile(os.path.join(BASE_DIR, name)):
                file_path = os.path.join(BASE_DIR, name)
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


@api_bp.route("/api/cobalt", methods=["POST"])
def cobalt_proxy():
    data = request.get_json(silent=True) or {}
    
    # Use localtunnel by default, fallback to direct local API if testing without localtunnel
    cobalt_url = os.environ.get("COBALT_URL", "http://127.0.0.1:9000/")
    
    try:
        # Forward the payload to the Cobalt server
        response = requests.post(
            cobalt_url,
            json=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Bypass-Tunnel-Reminder": "true",
                "User-Agent": "reclip-proxy/1.0"
            },
            timeout=30  # Give it some time just in case
        )
        
        json_resp = response.json()
        
        # Smart fallback for Instagram: If Cobalt couldn't find the video and returns a .jpg OR an error
        is_instagram = "instagram.com" in data.get("url", "").lower()
        is_jpg = json_resp.get("status") == "tunnel" and (json_resp.get("filename", "").endswith(".jpg") or json_resp.get("filename", "").endswith(".jpeg"))
        is_error = json_resp.get("status") == "error"

        if is_instagram and (is_jpg or is_error):
            try:
                import yt_dlp
                def get_ytdlp_url(cookiefile=None):
                    opts = {'format': 'best', 'quiet': True, 'no_warnings': True}
                    if cookiefile: opts['cookiefile'] = cookiefile
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(data.get("url"), download=False).get('url')
                
                video_url = None
                try:
                    # Try without cookies first (avoids 404 for public posts if cookies are bad)
                    video_url = get_ytdlp_url()
                except Exception:
                    # Fallback to cookies if it's private or requires login
                    cookie_path = os.path.join(BASE_DIR, 'www.instagram.com_cookies.txt')
                    
                    # On Vercel, load cookies from environment variable into a temp file
                    if os.environ.get("VERCEL") and os.environ.get("INSTAGRAM_COOKIES"):
                        cookie_path = "/tmp/instagram_cookies.txt"
                        if not os.path.exists(cookie_path):
                            with open(cookie_path, "w") as f:
                                # Vercel env vars sometimes replace newlines with spaces, so we parse properly
                                cookies_raw = os.environ.get("INSTAGRAM_COOKIES").replace("\\t", "\t").replace("\\n", "\n")
                                f.write(cookies_raw)
                    
                    video_url = get_ytdlp_url(cookie_path)
                    
                if video_url:
                    # Determine filename
                    filename = json_resp.get("filename", "")
                    if not filename or not (filename.endswith(".jpg") or filename.endswith(".jpeg")):
                        # Generate a safe default name if missing or not a replaceable image name
                        import re
                        safe_id = re.search(r'/(?:p|reel)/([^/?]+)', data.get("url", ""))
                        video_id = safe_id.group(1) if safe_id else "video"
                        filename = f"instagram_{video_id}.mp4"
                    else:
                        filename = filename.replace(".jpg", ".mp4").replace(".jpeg", ".mp4")

                    # Replace the Cobalt response with the yt-dlp direct URL
                    return jsonify({
                        "status": "tunnel",
                        "url": video_url,
                        "filename": filename
                    }), 200
            except Exception as ytdlp_e:
                print("yt-dlp fallback failed:", str(ytdlp_e))
                # Final fallback for image-only posts where yt-dlp fails because there is no video
                try:
                    import urllib.request
                    import re
                    req = urllib.request.Request(data.get("url"), headers={'User-Agent': 'Mozilla/5.0'})
                    html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
                    images = re.findall(r'<meta property="og:image" content="(.*?)"', html)
                    if images and "og:video" not in html:
                        image_url = images[0].replace("&amp;", "&")
                        # Generate a safe default name for the image
                        safe_id = re.search(r'/(?:p|reel)/([^/?]+)', data.get("url", ""))
                        video_id = safe_id.group(1) if safe_id else "image"
                        return jsonify({
                            "status": "tunnel",
                            "url": image_url,
                            "filename": f"instagram_{video_id}.jpg"
                        }), 200
                except Exception as image_e:
                    print("Image fallback failed:", str(image_e))
                pass # Fall back to returning the Cobalt JPG/Error if all fallbacks fail
        
        return jsonify(json_resp), response.status_code
    except Exception as e:
        # We explicitly format this as a Cobalt-style error so the frontend parses it correctly
        return jsonify({
            "status": "error",
            "error": {
                "code": "proxy_error",
                "message": f"Could not reach Cobalt API: {str(e)}"
            }
        }), 500