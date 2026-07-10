from src.routes.api import _resolve_direct_url_via_ytdlp

json_resp = {
    "status": "tunnel",
    "url": "https://storage-cuts-devel-reflects.trycloudflare.com/tunnel?id=...",
    "filename": "video.mp4"
}

target_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

raw_url = json_resp.get("url", "")
is_tunnel_url = (
    isinstance(raw_url, str)
    and ("trycloudflare.com" in raw_url or "/tunnel" in raw_url)
)

print(f"is_tunnel_url = {is_tunnel_url}")
if is_tunnel_url:
    try:
        from src.downloader import find_matching_cookie_file
        cookie_path = find_matching_cookie_file(target_url)
        print(f"DEBUG: Attempting yt-dlp resolution for {target_url} with cookie={cookie_path}")
        direct_url, direct_filename = _resolve_direct_url_via_ytdlp(target_url, cookie_path)
        print(f"DEBUG: yt-dlp returned direct_url={direct_url[:50] if direct_url else None}")
    except Exception as e:
        print("Exception:", e)
