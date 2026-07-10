import os
import re
import json
import shutil
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import jsonify

from src.config import BASE_DIR
from src.downloader import get_cookie_opts, augment_ytdlp_opts

def _get_ytdlp_cookie_path():
    """Return the best available Instagram cookie file path, or None."""
    cookie_path = os.path.join(BASE_DIR, "www.instagram.com_cookies.txt")
    if os.path.exists(cookie_path):
        if os.environ.get("VERCEL"):
            tmp_path = "/tmp/instagram_cookies.txt"
            try:
                shutil.copy2(cookie_path, tmp_path)
                return tmp_path
            except Exception:
                pass
        return cookie_path
    if os.environ.get("VERCEL") and os.environ.get("INSTAGRAM_COOKIES"):
        tmp_path = "/tmp/instagram_cookies.txt"
        try:
            raw = os.environ["INSTAGRAM_COOKIES"].replace("\\t", "\t").replace("\\n", "\n")
            with open(tmp_path, "w") as f:
                f.write(raw)
            return tmp_path
        except Exception:
            pass
    return None

def is_instagram_url(url):
    """Check if the given URL is an Instagram URL."""
    return "instagram.com" in url.lower()

def _load_cookies_from_file_or_frontend(frontend_cookies=None):
    """
    Build a cookies dict from frontend_cookies string or from the local cookie file.
    Returns a plain dict suitable for requests.get(cookies=...).
    """
    cookies = {}
    if frontend_cookies:
        # Parse pasted cookies (either Netscape or raw header format)
        if "\t" in frontend_cookies:
            for line in frontend_cookies.splitlines():
                if line.strip() and not line.startswith("#"):
                    parts = line.strip().split("\t")
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6]
        else:
            for pair in frontend_cookies.split(";"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    cookies[k.strip()] = v.strip()

    if not cookies:
        cookie_path = _get_ytdlp_cookie_path()
        if cookie_path and os.path.exists(cookie_path):
            with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip() or line.startswith("#"):
                        continue
                    parts = line.strip().split("\t")
                    if len(parts) >= 7:
                        cookies[parts[5]] = parts[6]
    return cookies


def _fetch_dp_via_api(username, cookies):
    """
    Fetch profile picture URL via Instagram's internal web_profile_info API.
    Works for public profiles without requiring full login cookies.
    Returns a dp_url string, or None if all attempts fail.
    """
    api_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-IG-App-ID": "936619743392459",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.instagram.com/{username}/",
        "X-CSRFToken": cookies.get("csrftoken", ""),
    }

    # Strategy 1: Instagram web_profile_info API (works for public accounts)
    try:
        api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        r = requests.get(api_url, headers=api_headers, cookies=cookies, timeout=12)
        if r.status_code == 200:
            data = r.json()
            user_data = (
                data.get("data", {}).get("user")
                or data.get("graphql", {}).get("user")
                or {}
            )
            # Try HD picture first, then standard
            for key in ("hd_profile_pic_url_info", "profile_pic_url_hd", "profile_pic_url"):
                val = user_data.get(key)
                if isinstance(val, dict):
                    val = val.get("url")
                if val and isinstance(val, str) and val.startswith("http"):
                    return val
    except Exception:
        pass

    # Strategy 2: Instagram GraphQL query (legacy but still works sometimes)
    try:
        gql_url = f"https://www.instagram.com/{username}/?__a=1&__d=dis"
        r = requests.get(gql_url, headers=api_headers, cookies=cookies, timeout=12)
        if r.status_code == 200:
            data = r.json()
            user_data = (
                data.get("graphql", {}).get("user")
                or data.get("data", {}).get("user")
                or {}
            )
            for key in ("profile_pic_url_hd", "profile_pic_url"):
                val = user_data.get(key)
                if val and isinstance(val, str) and val.startswith("http"):
                    return val
    except Exception:
        pass

    return None


def get_instagram_profile_dp(username, frontend_cookies=None):
    """
    Fetch the full-resolution profile picture URL for an Instagram username.
    Returns: A tuple of (Flask Response, HTTP status code).
    """
    if "instagram.com/" in username:
        # Extract username from a full URL if provided
        username = username.split("instagram.com/")[1].split("/")[0].split("?")[0]

    username = (username or "").strip().lstrip("@")
    if not username:
        return jsonify({"error": "Missing username"}), 400

    try:
        cookies = _load_cookies_from_file_or_frontend(frontend_cookies)

        # Priority 1: Instagram API (works for public accounts, much more reliable than HTML scraping)
        dp_url = _fetch_dp_via_api(username, cookies)

        # Priority 2: HTML scraping fallback
        if not dp_url:
            profile_url = f"https://www.instagram.com/{username}/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            try:
                res = requests.get(profile_url, headers=headers, cookies=cookies, timeout=10)
                if res.status_code == 200:
                    html = res.text
                    try:
                        og_matches = re.findall(r'<meta property="og:image" content="(.*?)"', html)
                        if og_matches:
                            candidate = og_matches[0].replace('&amp;', '&')
                            if "static.cdninstagram.com" not in candidate and "instagram_logo" not in candidate:
                                dp_url = candidate

                        if not dp_url:
                            hd_matches = re.findall(r'"profile_pic_url_hd"\s*:\s*"([^"]+)"', html)
                            if hd_matches:
                                dp_url = hd_matches[0].replace('\\/', '/').encode().decode('unicode-escape')
                            else:
                                pic_matches = re.findall(r'"profile_pic_url"\s*:\s*"([^"]+)"', html)
                                if pic_matches:
                                    dp_url = pic_matches[0].replace('\\/', '/').encode().decode('unicode-escape')
                    except Exception:
                        pass
            except Exception:
                pass

        if not dp_url:
            return jsonify({
                "status": "error",
                "error": {
                    "code": "instagram.dp.fail",
                    "message": (
                        "Server error — could not fetch profile picture. "
                        "Instagram may have blocked this request. "
                        "Try adding valid Instagram cookies in Settings, then retry."
                    )
                }
            }), 404

        return jsonify({
            "status": "tunnel",
            "url": dp_url,
            "filename": f"{username}_dp.jpg"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": {"code": "instagram.dp.error", "message": f"Could not fetch DP: {str(e)}"}
        }), 500


def get_instagram_audio(post_url, frontend_cookies=None):
    """
    Extracts the direct audio preview URL from an Instagram Reels audio page.
    """
    match = re.search(r"/reels/audio/(\d+)", post_url)
    if not match:
        return jsonify({"status": "error", "error": {"code": "link.invalid", "message": "Invalid Instagram Audio URL"}}), 400

    audio_id = match.group(1)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "X-IG-App-ID": "936619743392459",
    }

    cookies = {}

    if frontend_cookies and frontend_cookies.get("mode", "none") != "none":
        try:
            cookie_opts, temp_cookie_file = get_cookie_opts(frontend_cookies, post_url)
            cookie_path = cookie_opts.get("cookiefile")
            if cookie_path and os.path.exists(cookie_path):
                with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if not line.strip() or line.startswith("#"):
                            continue
                        parts = line.strip().split("\t")
                        if len(parts) >= 7:
                            cookies[parts[5]] = parts[6]
            if temp_cookie_file and os.path.exists(temp_cookie_file):
                try:
                    os.remove(temp_cookie_file)
                except OSError:
                    pass
        except Exception:
            pass

    if not cookies:
        cookie_path = _get_ytdlp_cookie_path()
        if cookie_path and os.path.exists(cookie_path):
            try:
                with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if not line.strip() or line.startswith("#"):
                            continue
                        parts = line.strip().split("\t")
                        if len(parts) >= 7:
                            cookies[parts[5]] = parts[6]
            except Exception:
                pass

    html = None
    status_code = None
    if cookies:
        try:
            r = requests.get(post_url, headers=headers, cookies=cookies, timeout=10)
            status_code = r.status_code
            html = r.text
        except requests.exceptions.TooManyRedirects:
            pass
        except Exception:
            pass

    if html is None:
        try:
            r = requests.get(post_url, headers=headers, timeout=10)
            status_code = r.status_code
            html = r.text
        except Exception as e:
            return jsonify({"status": "error", "error": {"code": "proxy_error", "message": f"Failed to fetch page: {str(e)}"}}), 500

    if status_code != 200:
        return jsonify({"status": "error", "error": {"code": "fetch.fail", "message": f"Instagram returned status {status_code}"}}), status_code

    audio_url = None
    patterns = [
        r'"progressive_sound_url"\s*:\s*"([^"]+)"',
        r'"fast_start_progressive_sound_url"\s*:\s*"([^"]+)"',
        r'"audio_src"\s*:\s*"([^"]+)"',
        r'"audio_asset_url"\s*:\s*"([^"]+)"',
    ]

    for pat in patterns:
        m = re.search(pat, html)
        if m:
            audio_url = m.group(1)
            break

    if not audio_url:
        m_cdn = re.search(r'https?:\/\/[^\s"\'\\<>]+?\.fbcdn\.net\/[^\s"\'\\<>]+?\.(?:mp3|m4a|mp4)[^\s"\'\\<>]*', html)
        if m_cdn:
            audio_url = m_cdn.group(0)

    if not audio_url and "/reels/audio/" in post_url.lower():
        # Instagram's internal API no longer provides progressive_sound_url
        # Workaround: find the first Reel shortcode on this audio page and download the Reel instead.
        m_shortcode = re.search(r'"shortcode"\s*:\s*"([A-Za-z0-9_-]+)"', html)
        if m_shortcode:
            shortcode = m_shortcode.group(1)
            reel_url = f"https://www.instagram.com/reel/{shortcode}/"
            # Attempt to use yt-dlp to download this Reel!
            fallback_resp = get_instagram_media_fallback(
                reel_url,
                {"filename": f"instagram_audio_{audio_id}.mp3"},
                frontend_cookies
            )
            if fallback_resp:
                return fallback_resp

    if not audio_url:
        return jsonify({
            "status": "error",
            "error": {
                "code": "instagram.no_audio",
                "message": "Instagram blocks direct downloads from /reels/audio/ pages. To get this audio, copy the link of ANY Reel using it, paste it here, and select 'Audio Only'."
            }
        }), 404

    try:
        audio_url = audio_url.replace("\\/", "/").encode().decode('unicode-escape')
    except Exception:
        pass

    filename = f"instagram_audio_{audio_id}.mp3"
    return jsonify({
        "status": "tunnel",
        "url": audio_url,
        "filename": filename
    }), 200


def get_instagram_media_fallback(post_url, cobalt_resp, frontend_cookies=None, force_no_cookies=False):
    """
    yt-dlp fallback for Instagram.
    - Uses frontend cookie settings if provided (unless force_no_cookies=True)
    - Handles multi-item carousels → returns picker format
    - Returns a Flask Response or None if fallback also failed
    """
    try:
        import yt_dlp

        cookie_opts = {}
        temp_cookie_file = None

        if not force_no_cookies:
            if frontend_cookies and frontend_cookies.get("mode", "none") != "none":
                try:
                    cookie_opts, temp_cookie_file = get_cookie_opts(frontend_cookies, post_url)
                except Exception:
                    pass

        if not cookie_opts:
            cookie_path = _get_ytdlp_cookie_path()
            if cookie_path:
                cookie_opts = {"cookiefile": cookie_path}

        def _extract(opts_extra=None):
            opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": False,
            }
            if cookie_opts:
                opts.update(cookie_opts)
            if opts_extra:
                opts.update(opts_extra)
            opts = augment_ytdlp_opts(opts)
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(post_url, download=False)

        info = None
        try:
            info = _extract({"cookiefile": None, "cookiesfrombrowser": None} if not cookie_opts else None)
        except Exception:
            pass

        if not info and cookie_opts:
            try:
                info = _extract()
            except Exception:
                pass

        if not info:
            raise Exception("No video media info extracted by yt-dlp. Triggering photo fallback.")

        entries = None
        if info.get("_type") == "playlist" or "entries" in info:
            entries = [e for e in (info.get("entries") or []) if e]

        if entries and len(entries) > 1:
            picker_items = []
            for entry in entries:
                item_url = entry.get("url") or entry.get("webpage_url")
                if not item_url:
                    continue
                formats = entry.get("formats") or []
                has_video = any(
                    (f.get("vcodec") or "none").lower() != "none" for f in formats
                )
                has_audio_only = (not has_video) and any(
                    (f.get("acodec") or "none").lower() != "none" for f in formats
                )
                item_type = "photo" if (not has_video and not has_audio_only) else "video"
                thumb = entry.get("thumbnail") or ""
                picker_items.append({
                    "url": item_url,
                    "type": item_type,
                    "thumb": thumb
                })

            if picker_items:
                if temp_cookie_file:
                    try:
                        os.remove(temp_cookie_file)
                    except OSError:
                        pass
                return jsonify({"status": "picker", "picker": picker_items}), 200

        video_url = None
        target_dict = entries[0] if entries else info
        video_url = target_dict.get("url")

        if not video_url and target_dict.get("requested_formats"):
            for f in target_dict["requested_formats"]:
                if (f.get("vcodec") or "none").lower() != "none" and f.get("url"):
                    video_url = f["url"]
                    break

        if not video_url and target_dict.get("formats"):
            prog_fmts = [
                f for f in target_dict["formats"]
                if f.get("url")
                and (f.get("vcodec") or "none").lower() != "none"
                and (f.get("acodec") or "none").lower() != "none"
            ]
            if prog_fmts:
                video_url = prog_fmts[-1]["url"]
            else:
                vid_fmts = [
                    f for f in target_dict["formats"]
                    if f.get("url") and (f.get("vcodec") or "none").lower() != "none"
                ]
                if vid_fmts:
                    video_url = vid_fmts[-1]["url"]
                else:
                    any_fmts = [f for f in target_dict["formats"] if f.get("url")]
                    if any_fmts:
                        video_url = any_fmts[-1]["url"]

        if not video_url:
            raise Exception("No video URL found by yt-dlp")

        filename = cobalt_resp.get("filename", "") or cobalt_resp.get("output", {}).get("filename", "")
        if not filename or filename.endswith(".jpg") or filename.endswith(".jpeg"):
            safe_match = re.search(r"/(?:p|reel|tv)/([^/?]+)", post_url)
            vid_id = safe_match.group(1) if safe_match else "video"
            filename = f"instagram_{vid_id}.mp4"
        else:
            filename = filename.replace(".jpg", ".mp4").replace(".jpeg", ".mp4")

        if temp_cookie_file:
            try:
                os.remove(temp_cookie_file)
            except OSError:
                pass

        return jsonify({"status": "tunnel", "url": video_url, "filename": filename}), 200

    except Exception as ytdlp_e:
        print("yt-dlp fallback failed:", str(ytdlp_e))

    # Image Fallback: Execute if yt-dlp throws an exception OR fails to find a video URL
    try:
        import urllib.request
        req = urllib.request.Request(post_url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8")
        images = re.findall(r'<meta property="og:image" content="(.*?)"', html)
        if images and "og:video" not in html and not any(x in post_url.lower() for x in ["/reel/", "/stories/"]):
            image_url = images[0].replace("&amp;", "&")
            if "static.cdninstagram.com/rsrc.php" not in image_url:
                safe_match = re.search(r"/(?:p|reel)/([^/?]+)", post_url)
                vid_id = safe_match.group(1) if safe_match else "image"
                return jsonify({
                    "status": "tunnel",
                    "url": image_url,
                    "filename": f"instagram_{vid_id}.jpg"
                }), 200
    except Exception:
        pass

    return None

# Public Cobalt API instances to try in sequence if the local one fails.
# These are community-maintained instances; the list may need updating.
_COBALT_PUBLIC_FALLBACKS = [
    # "https://api.cobalt.tools/",
    # "https://cobalt.api.horse/",
    # "https://co.wuk.sh/",
]


def _try_cobalt_instances(url, request_data, primary_cobalt_url):
    """
    Try the primary local Cobalt instance first, then public fallbacks.
    Returns the parsed JSON response dict, or None if all fail.
    """
    candidates = []
    if primary_cobalt_url:
        candidates.append(primary_cobalt_url)
    candidates.extend(_COBALT_PUBLIC_FALLBACKS)

    for cobalt_url in candidates:
        try:
            response = requests.post(
                cobalt_url,
                json=request_data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Bypass-Tunnel-Reminder": "true",
                    "User-Agent": "instantreels-proxy/1.0"
                },
                timeout=10
            )
            if response.status_code not in (200, 400):
                continue
            json_resp = response.json()
            filename_val = json_resp.get("filename") or json_resp.get("output", {}).get("filename") or ""
            is_jpg = (json_resp.get("status") in ("tunnel", "local-processing")) and (
                filename_val.endswith(".jpg") or filename_val.endswith(".jpeg")
            )
            is_error = json_resp.get("status") == "error"
            if not is_error and not is_jpg:
                return json_resp
        except Exception:
            continue

    return None


def get_instagram_story(url, frontend_cookies=None):
    """
    Download an Instagram Story by calling the Instagram reels/media feed API.
    Requires a valid sessionid cookie. Returns a Flask Response.
    """
    # Extract user_id and media_id from the URL
    # URL format: /stories/<username>/<media_id>/  OR has reel_owner_id / reel_id query params
    media_id = None
    user_id = None

    # Try to get user_id from query params (most reliable)
    qs_owner = re.search(r'reel_owner_id=(\d+)', url)
    qs_reel  = re.search(r'reel_id=(\d+)', url)
    if qs_owner:
        user_id = qs_owner.group(1)
    if qs_reel:
        user_id = qs_reel.group(1)  # reel_id IS the owner user_id for story reels

    # Extract media_id from path
    path_match = re.search(r'/stories/[^/]+/(\d+)', url)
    if path_match:
        media_id = path_match.group(1)

    # Load cookies
    cookies = _load_cookies_from_file_or_frontend(frontend_cookies)
    session_id = cookies.get("sessionid")

    if not session_id:
        return jsonify({
            "status": "error",
            "error": {
                "code": "instagram.story.no_auth",
                "message": (
                    "Instagram Stories require you to be logged in. "
                    "Open Settings → Service Cookies Setup → INSTAGRAM, "
                    "paste your Instagram cookies (must include sessionid), and try again."
                )
            }
        }), 401

    api_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-IG-App-ID": "936619743392459",
        "X-CSRFToken": cookies.get("csrftoken", ""),
        "Referer": "https://www.instagram.com/",
    }

    # Strategy 1: Fetch via reel_ids API (works best for story reels)
    story_media_url = None
    story_filename = None
    story_thumb = None
    is_video = False

    if user_id:
        try:
            api_url = f"https://www.instagram.com/api/v1/feed/reels_media/?reel_ids={user_id}"
            r = requests.get(api_url, headers=api_headers, cookies=cookies, timeout=15)
            if r.status_code == 200:
                data = r.json()
                reels = data.get("reels") or data.get("reels_media") or {}
                reel = reels.get(user_id) or (list(reels.values())[0] if reels else None)
                items = (reel or {}).get("items") or []

                # Find the specific story item by media_id
                target_item = None
                for item in items:
                    if media_id and str(item.get("id", "")).startswith(str(media_id)):
                        target_item = item
                        break
                # Fallback: use the most recent item
                if not target_item and items:
                    target_item = items[0]

                if target_item:
                    media_type = target_item.get("media_type", 1)
                    is_video = (media_type == 2)

                    if is_video:
                        video_versions = target_item.get("video_versions") or []
                        if video_versions:
                            # Pick highest quality
                            best = max(video_versions, key=lambda v: (v.get("width", 0) * v.get("height", 0)))
                            story_media_url = best.get("url")
                    else:
                        image_versions = target_item.get("image_versions2", {}).get("candidates") or []
                        if image_versions:
                            best = max(image_versions, key=lambda v: (v.get("width", 0) * v.get("height", 0)))
                            story_media_url = best.get("url")

                    # Thumbnail
                    thumb_candidates = target_item.get("image_versions2", {}).get("candidates") or []
                    if thumb_candidates:
                        story_thumb = thumb_candidates[-1].get("url")

                    if story_media_url:
                        ext = "mp4" if is_video else "jpg"
                        pk = target_item.get("id") or media_id or "story"
                        story_filename = f"instagram_story_{pk}.{ext}"
        except Exception as e:
            print(f"Story API (reels_media) failed: {e}")

    # Strategy 2: Try yt-dlp with cookies as a fallback
    if not story_media_url:
        try:
            fallback = get_instagram_media_fallback(
                url,
                {"status": "fallback", "filename": ""},
                frontend_cookies,
                force_no_cookies=False
            )
            if fallback:
                return fallback
        except Exception:
            pass

    if not story_media_url:
        return jsonify({
            "status": "error",
            "error": {
                "code": "instagram.story.fail",
                "message": (
                    "Could not download this story. It may have expired (stories last 24 hours), "
                    "or the account is private and your cookies do not have access. "
                    "Ensure your Instagram sessionid cookie is valid and try again."
                )
            }
        }), 404

    return jsonify({
        "status": "tunnel",
        "url": story_media_url,
        "filename": story_filename,
        "thumb": story_thumb
    }), 200


def handle_instagram_request(url, request_data, frontend_cookies=None, cobalt_url=None):
    """
    Main router for Instagram requests.
    If it's an audio URL, fetch audio directly.
    If it's a story URL, use the dedicated story downloader.
    Otherwise, run a strict sequential fallback:
      1. Cobalt API (local instance + public fallbacks)
      2. yt-dlp (no cookies)
      3. yt-dlp (with cookies)
    """
    if "/reels/audio/" in url.lower():
        return get_instagram_audio(url, frontend_cookies)

    # Intercept Story URLs — must be handled before the profile URL check
    if "/stories/" in url.lower():
        return get_instagram_story(url, frontend_cookies)

    # Intercept Profile URLs (does not contain /p/, /reel/, /tv/, /stories/)
    # This prevents the router from sending profile URLs to Cobalt/yt-dlp which would crash.
    if re.search(r'instagram\.com/([^/]+)/?(\?.*)?$', url.lower()) and not any(x in url.lower() for x in ['/p/', '/reel/', '/reels/', '/tv/', '/stories/']):
        return get_instagram_profile_dp(url, frontend_cookies)

    # 1. Try Cobalt (local instance natively supports carousels)
    cobalt_json = _try_cobalt_instances(url, request_data, cobalt_url)
    if cobalt_json:
        return jsonify(cobalt_json), 200

    # 2. Try yt-dlp without cookies (fastest for public reels if Cobalt fails)
    yt_no_cookies = get_instagram_media_fallback(
        url,
        {"status": "fallback", "filename": ""},
        frontend_cookies,
        force_no_cookies=True
    )
    if yt_no_cookies:
        return yt_no_cookies

    # 3. Try yt-dlp WITH cookies (bypasses login walls for private/rate-limited reels)
    yt_with_cookies = get_instagram_media_fallback(
        url,
        {"status": "fallback", "filename": ""},
        frontend_cookies,
        force_no_cookies=False
    )
    if yt_with_cookies:
        return yt_with_cookies

    # All failed — return a clear, actionable error
    has_cookies = bool(_get_ytdlp_cookie_path())
    if has_cookies:
        message = (
            "Download failed even with your cookies. "
            "Instagram may have temporarily rate-limited this IP. "
            "Please wait a few minutes and try again."
        )
    else:
        message = (
            "Instagram blocked this download (login required). "
            "To fix this: open Settings → Service Cookies Setup → INSTAGRAM, "
            "paste your Instagram cookies, and try again."
        )

    return jsonify({
        "status": "error",
        "error": {
            "code": "instagram.fail",
            "message": message
        }
    }), 500
