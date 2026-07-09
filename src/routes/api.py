import os
import re  # BUG-018 FIX: moved to top level (was imported inside nested functions)
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, request, jsonify, redirect
from src.config import BASE_DIR, USER_DIR
import requests
from urllib.parse import urlparse, parse_qs
from src.metrics import track_request

# BUG-021 FIX: Characters illegal in filenames on Windows and POSIX
_ILLEGAL_FILENAME_CHARS = set('\\/:*?"<>|\n\r\t')

# ---------------------------------------------------------------------------
# Fix 3: In-memory URL resolution cache (60s TTL)
# Avoids re-running yt_dlp.extract_info() for the same URL within 60 seconds.
# ---------------------------------------------------------------------------
_url_cache = {}          # { original_url: (resolved_url, filename, timestamp) }
_url_cache_ttl = 60      # seconds
_url_cache_lock = threading.Lock()


def _cache_get(url):
    """Return (resolved_url, filename) if a fresh cached entry exists, else None."""
    with _url_cache_lock:
        entry = _url_cache.get(url)
        if entry and (time.time() - entry[2]) < _url_cache_ttl:
            return entry[0], entry[1]
        return None


def _cache_set(url, resolved_url, filename):
    """Store a resolved URL in the cache."""
    with _url_cache_lock:
        _url_cache[url] = (resolved_url, filename, time.time())


api_bp = Blueprint("api", __name__)


@api_bp.route("/api/cookie-files")
def list_cookie_files():
    files = []
    try:
        for name in os.listdir(USER_DIR):
            if name.endswith(".txt") and os.path.isfile(os.path.join(USER_DIR, name)):
                file_path = os.path.join(USER_DIR, name)
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


@api_bp.route("/api/cobalt", methods=["POST"], strict_slashes=False)
def cobalt_proxy():
    data = request.get_json(silent=True) or {}
    
    # Extract cookies_data before forwarding to Cobalt (Cobalt doesn't expect this field)
    frontend_cookies = data.pop("cookies_data", None)
    
    # Use localtunnel by default, fallback to direct local API if testing without localtunnel
    cobalt_url = os.environ.get("COBALT_URL", "http://127.0.0.1:9000/")
    
    target_url = data.get("url", "") or ""

    # Fix 3: Check the URL cache before doing any network work
    cached = _cache_get(target_url)
    if cached:
        cached_url, cached_filename = cached
        track_request(target_url, success=True)
        # Return JSON — /api/cobalt is called by frontend JS fetch(), not browser navigation
        return jsonify({"status": "tunnel", "url": cached_url, "filename": cached_filename}), 200
    
    from src.instagram import is_instagram_url, handle_instagram_request
    if is_instagram_url(target_url):
        # We process Instagram requests using our specialized module
        # This gives us access to custom HTML audio scrapers for /reels/audio/ 
        result = handle_instagram_request(target_url, data, frontend_cookies, cobalt_url)
        
        success = False
        if isinstance(result, tuple) and len(result) >= 2:
            success = (result[1] == 200)
        elif hasattr(result, "status_code"):
            success = (result.status_code == 200)
            
        track_request(target_url, success=success)
        return result
        
    try:
        # Fix 2: Reduced Cobalt timeout from 30s → 8s
        response = requests.post(
            cobalt_url,
            json=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Bypass-Tunnel-Reminder": "true",
                "User-Agent": "reclip-proxy/1.0"
            },
            timeout=8  # Fix 2: was 30s — lower so yt-dlp fallback starts faster
        )
        
        try:
            json_resp = response.json()
        except Exception as json_e:
            track_request(target_url, success=False)
            return jsonify({
                "status": "error",
                "error": {
                    "code": "proxy_error",
                    "message": f"Cobalt returned a non-JSON response: {str(json_e)}"
                }
            }), 500
        is_instagram = "instagram.com" in target_url.lower()
        is_jpg = json_resp.get("status") == "tunnel" and (json_resp.get("filename", "").endswith(".jpg") or json_resp.get("filename", "").endswith(".jpeg"))
        is_error = json_resp.get("status") == "error"
        is_rate_limit = json_resp.get("status") == "rate-limit" or response.status_code == 429

        if is_error or is_rate_limit or (is_instagram and is_jpg):
            try:
                import yt_dlp
                from src.downloader import find_matching_cookie_file, get_cookie_opts
                
                # Check for frontend provided cookies first
                cookie_opts = {}
                temp_cookie_file = None
                
                if frontend_cookies and frontend_cookies.get("mode", "none") != "none":
                    try:
                        cookie_opts, temp_cookie_file = get_cookie_opts(frontend_cookies, target_url)
                    except Exception:
                        pass
                        
                cookie_path = cookie_opts.get("cookiefile")
                
                if not cookie_path:
                    # Fallback to locally configured cookie file
                    cookie_path = find_matching_cookie_file(target_url)
                
                def get_ytdlp_url(cookiefile=None):
                    opts = {'format': 'best', 'quiet': True, 'no_warnings': True}
                    if cookiefile: opts['cookiefile'] = cookiefile
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(target_url, download=False)
                        url = info.get('url')
                        if not url and 'formats' in info:
                            # Filter formats that have a direct URL
                            valid_formats = [f for f in info['formats'] if f.get('url')]
                            if valid_formats:
                                # Prioritize progressive formats
                                prog = [f for f in valid_formats if 'progressive' in f.get('format_note', '').lower() or 'progressive' in f.get('url', '').lower()]
                                if prog:
                                    url = prog[-1]['url']
                                else:
                                    # Fallback to the last valid format that has a URL
                                    url = valid_formats[-1]['url']
                        return info, url
                
                info = None
                video_url = None
                try:
                    # Try with matching cookie file if it exists, otherwise without cookies first
                    info, video_url = get_ytdlp_url(cookie_path)
                except Exception as e:
                    # If we tried with cookies and failed, try without cookies as a fail-safe
                    if cookie_path:
                        try:
                            info, video_url = get_ytdlp_url()
                        except Exception:
                            raise e
                    else:
                        raise e
                    
                if video_url:
                    # Determine filename
                    filename = json_resp.get("filename", "")
                    is_audio_only = data.get("isAudioOnly", False)
                    if is_instagram and is_jpg and filename:
                        ext = ".mp3" if is_audio_only else ".mp4"
                        filename = filename.replace(".jpg", ext).replace(".jpeg", ext)
                        
                    if not filename or filename.endswith(".jpg") or filename.endswith(".jpeg"):
                        title = info.get("title") if info else None
                        if title:
                            safe_title = "".join(c for c in title if c not in _ILLEGAL_FILENAME_CHARS).strip()[:80].strip()
                            ext = ".mp3" if is_audio_only else ".mp4"
                            filename = f"{safe_title}{ext}"
                        else:
                            # Generate a safe default name
                            video_id = "video"
                            if is_instagram:
                                safe_id = re.search(r'/(?:p|reel)/([^/?]+)', target_url)
                                video_id = safe_id.group(1) if safe_id else "instagram"
                            elif "youtube.com" in target_url or "youtu.be" in target_url:
                                parsed_url = urlparse(target_url)
                                if parsed_url.netloc == "youtu.be":
                                    video_id = parsed_url.path.strip("/")
                                else:
                                    qs = parse_qs(parsed_url.query)
                                    if "v" in qs:
                                        video_id = qs["v"][0]
                            ext = ".mp3" if is_audio_only else ".mp4"
                            filename = f"video_{video_id}{ext}"

                    # Fix 3: Cache the resolved URL
                    _cache_set(target_url, video_url, filename)
                    track_request(target_url, success=True)
                    # Return JSON — frontend JS fetch() parses this to get the download URL
                    return jsonify({"status": "tunnel", "url": video_url, "filename": filename}), 200
            except Exception as ytdlp_e:
                print("yt-dlp fallback failed:", str(ytdlp_e))
                # Final fallback for image-only posts on Instagram where yt-dlp fails
                if is_instagram:
                    try:
                        import urllib.request
                        req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
                        html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
                        images = re.findall(r'<meta property="og:image" content="(.*?)"', html)
                        if images and "og:video" not in html and "/reel/" not in target_url.lower():
                            image_url = images[0].replace("&amp;", "&")
                            if "static.cdninstagram.com/rsrc.php" not in image_url:
                                safe_id = re.search(r'/(?:p|reel)/([^/?]+)', target_url)
                                video_id = safe_id.group(1) if safe_id else "image"
                                track_request(target_url, success=True)
                                return jsonify({
                                    "status": "tunnel",
                                    "url": image_url,
                                    "filename": f"instagram_{video_id}.jpg"
                                }), 200
                    except Exception as image_e:
                        print("Image fallback failed:", str(image_e))
                        
                if temp_cookie_file and os.path.exists(temp_cookie_file):
                    try:
                        os.remove(temp_cookie_file)
                    except OSError:
                        pass
                pass # Fall back to returning the Cobalt Error if all fallbacks fail
        
        # Track successful resolution
        if response.status_code == 200 and json_resp.get("status") in ("tunnel", "redirect"):
            track_request(target_url, success=True)
            
            # Fix 3: Cache resolved Cobalt URL for future lookups
            cobalt_direct_url = json_resp.get("url", "")
            if cobalt_direct_url and "/tunnel" not in cobalt_direct_url:
                resolved_filename = json_resp.get("filename", "video.mp4")
                _cache_set(target_url, cobalt_direct_url, resolved_filename)
            # Return JSON as-is — frontend JS fetch() expects {status, url, filename}

            # Fix Cobalt's dead internal trycloudflare URLs by rewriting them to use our own proxy
            if "url" in json_resp:
                raw_url = json_resp["url"]
                # Only rewrite Cobalt's ephemeral trycloudflare.com tunnel URLs;
                # direct CDN URLs (fbcdn.net, cdninstagram.com, etc.) must NOT be touched.
                if "trycloudflare.com" in raw_url and "/tunnel" in raw_url:
                    json_resp["url"] = re.sub(
                        r'https?://[^/]+\.trycloudflare\.com/tunnel',
                        request.host_url.rstrip('/') + '/tunnel',
                        raw_url
                    )
                
        elif response.status_code == 200 and json_resp.get("status") == "picker" and "picker" in json_resp:
            track_request(target_url, success=True)
            for item in json_resp["picker"]:
                if "url" in item and "trycloudflare.com" in item["url"] and "/tunnel" in item["url"]:
                    item["url"] = re.sub(
                        r'https?://[^/]+\.trycloudflare\.com/tunnel',
                        request.host_url.rstrip('/') + '/tunnel',
                        item["url"]
                    )

                    
        elif json_resp.get("status") == "error":
            track_request(target_url, success=False)
            
        return jsonify(json_resp), response.status_code
    except Exception as e:
        track_request(data.get("url"), success=False)
        # We explicitly format this as a Cobalt-style error so the frontend parses it correctly
        return jsonify({
            "status": "error",
            "error": {
                "code": "proxy_error",
                "message": f"Could not reach Cobalt API: {str(e)}"
            }
        }), 500


# ---------------------------------------------------------------------------
# Stream proxy — unchanged (already fixed in previous session)
# ---------------------------------------------------------------------------

@api_bp.route("/tunnel", methods=["GET"])
def tunnel_proxy():
    """
    Proxies Cobalt's internal tunnel endpoint so we don't rely on Cobalt's
    flaky quick-tunnels (trycloudflare.com) which frequently get banned.
    """
    cobalt_url = os.environ.get("COBALT_URL", "http://127.0.0.1:9000/")
    target_tunnel = cobalt_url.rstrip('/') + "/tunnel"
    
    try:
        upstream = requests.get(
            target_tunnel,
            params=request.args,
            stream=True,
            timeout=60,
            allow_redirects=False
        )
        
        # Do NOT exclude content-length so client can track download progress
        excluded_headers = ['content-encoding', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in upstream.raw.headers.items()
                   if name.lower() not in excluded_headers]
                   
        filename = request.args.get("filename")
        if filename:
            # Remove any existing Content-Disposition
            headers = [h for h in headers if h[0].lower() != 'content-disposition']
            headers.append(('Content-Disposition', f'attachment; filename="{filename}"'))
                   
        def generate():
            # Fix 4: Increased chunk size from 65536 (64KB) to 524288 (512KB)
            for chunk in upstream.iter_content(chunk_size=524288):
                if chunk:
                    yield chunk

        from flask import Response
        return Response(
            generate(),
            status=upstream.status_code,
            headers=headers
        )
    except Exception as e:
        return f"Tunnel Proxy Error: {str(e)}", 500


@api_bp.route("/api/stream", methods=["GET"])
def stream_download():
    target_url = request.args.get("url")
    filename = request.args.get("filename", "video.mp4")
    
    if not target_url:
        return "Missing URL", 400
        
    try:
        parsed_url = urlparse(target_url)
        if parsed_url.scheme not in ("http", "https"):
            return "Invalid URL scheme", 400
            
        hostname = parsed_url.hostname
        if not hostname:
            return "Invalid URL hostname", 400
            
        hostname_lower = hostname.lower()
        if hostname_lower in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]", "::1"):
            return "Access to local host is forbidden", 400
            
        import socket
        try:
            ip = socket.gethostbyname(hostname)
            ip_parts = [int(x) for x in ip.split('.')]
            if len(ip_parts) == 4:
                if (ip_parts[0] == 127 or
                    ip_parts[0] == 0 or
                    ip_parts[0] == 10 or
                    (ip_parts[0] == 172 and 16 <= ip_parts[1] <= 31) or
                    (ip_parts[0] == 192 and ip_parts[1] == 168) or
                    (ip_parts[0] == 169 and ip_parts[1] == 254)):
                    return "Access to private IP is forbidden", 400
        except Exception:
            pass
    except Exception as parse_err:
        return f"Invalid URL: {str(parse_err)}", 400

    # Fix 1: Issue a 302 redirect directly to the CDN URL.
    # The client (browser) will follow the redirect and download straight from the source.
    # This eliminates the double-download bottleneck where the server was re-proxying the full file.
    return redirect(target_url, code=302)


@api_bp.route("/api/download", methods=["GET"])
def direct_download():
    target_url = request.args.get("url")
    if not target_url:
        return "Missing url parameter", 400
    
    filename_param = request.args.get("filename")
    
    # 1. Try resolving using Cobalt first
    cobalt_url = os.environ.get("COBALT_URL", "http://127.0.0.1:9000/")
    resolved_url = None
    resolved_filename = filename_param or "video.mp4"
    
    try:
        cobalt_payload = {
            "url": target_url,
            "videoCodec": "h264",
        }
        response = requests.post(
            cobalt_url,
            json=cobalt_payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Bypass-Tunnel-Reminder": "true",
                "User-Agent": "reclip-proxy/1.0"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            json_resp = response.json()
            is_jpg = json_resp.get("status") == "tunnel" and (json_resp.get("filename", "").endswith(".jpg") or json_resp.get("filename", "").endswith(".jpeg"))
            is_instagram = "instagram.com" in target_url.lower()
            
            if json_resp.get("status") in ("tunnel", "redirect") and not (is_instagram and is_jpg):
                resolved_url = json_resp.get("url")
                if not filename_param:
                    resolved_filename = json_resp.get("filename") or resolved_filename
    except Exception as e:
        print("Cobalt resolution failed, falling back to yt-dlp:", str(e))
    # 2. Fall back to yt-dlp if Cobalt failed
    if not resolved_url:
        try:
            import yt_dlp
            from src.downloader import find_matching_cookie_file
            
            cookie_path = find_matching_cookie_file(target_url)
            
            opts = {'format': 'best', 'quiet': True, 'no_warnings': True}
            if cookie_path:
                opts['cookiefile'] = cookie_path
                
            info = None
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(target_url, download=False)
                    resolved_url = info.get('url')
            except Exception as ytdlp_err:
                if cookie_path:
                    try:
                        opts_no_cookies = {'format': 'best', 'quiet': True, 'no_warnings': True}
                        with yt_dlp.YoutubeDL(opts_no_cookies) as ydl_no_cookies:
                            info = ydl_no_cookies.extract_info(target_url, download=False)
                            resolved_url = info.get('url')
                    except Exception:
                        raise ytdlp_err
                else:
                    raise ytdlp_err
            
            if resolved_url and not filename_param:
                title = info.get("title") if info else None
                if title:
                    # BUG-021 FIX: proper illegal char set
                    safe_title = "".join(c for c in title if c not in _ILLEGAL_FILENAME_CHARS).strip()[:80].strip()
                    resolved_filename = f"{safe_title}.mp4"
                else:
                    video_id = "video"
                    if "instagram.com" in target_url:
                        safe_id = re.search(r'/(?:p|reel)/([^/?]+)', target_url)
                        video_id = safe_id.group(1) if safe_id else "instagram"
                    elif "youtube.com" in target_url or "youtu.be" in target_url:
                        parsed_url = urlparse(target_url)
                        if parsed_url.netloc == "youtu.be":
                            video_id = parsed_url.path.strip("/")
                        else:
                            from urllib.parse import parse_qs
                            qs = parse_qs(parsed_url.query)
                            if "v" in qs:
                                video_id = qs["v"][0]
                    resolved_filename = f"video_{video_id}.mp4"
                    
        except Exception as fallback_e:
            return f"Failed to download or resolve URL: {str(fallback_e)}", 500

    # 3. Fix 1+3: Cache and redirect directly to the resolved CDN URL
    if not resolved_url:
        track_request(target_url, success=False)
        return "Failed to resolve stream URL", 500

    _cache_set(target_url, resolved_url, resolved_filename)
    track_request(target_url, success=True)
    return redirect(resolved_url, code=302)