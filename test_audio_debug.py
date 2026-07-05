"""Debug Instagram audio download behavior."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import requests
import yt_dlp

TEST_URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.instagram.com/reel/DCXxxxxxxx/"
RENDER = "https://instant-02.onrender.com"


def ffprobe_audio(path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return "no ffprobe"
    cmd = [
        ffprobe, "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=codec_name", "-of", "json", path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    try:
        data = json.loads(r.stdout or "{}")
        streams = data.get("streams", [])
        return f"{len(streams)} audio stream(s): {[s.get('codec_name') for s in streams]}"
    except Exception as e:
        return f"parse error: {e} stderr={r.stderr[:200]}"


def list_formats(url):
    opts = {"quiet": True, "no_warnings": True, "ignore_no_formats_error": True}
    cookie = os.path.join(os.path.dirname(__file__), "www.instagram.com_cookies.txt")
    if os.path.exists(cookie):
        opts["cookiefile"] = cookie
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    formats = info.get("formats") or []
    print(f"Title: {info.get('title')}")
    print(f"Total formats: {len(formats)}")
    for f in formats[-15:]:
        print(
            f"  id={f.get('format_id')} ext={f.get('ext')} "
            f"{f.get('height')}p v={f.get('vcodec')} a={f.get('acodec')} "
            f"tbr={f.get('tbr')}"
        )
    return info


def try_download(url, fmt, outdir):
    opts = {
        "format": fmt,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(outdir, "test.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    cookie = os.path.join(os.path.dirname(__file__), "www.instagram.com_cookies.txt")
    if os.path.exists(cookie):
        opts["cookiefile"] = cookie
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)
    files = [os.path.join(outdir, f) for f in os.listdir(outdir)]
    return files


def test_render(url):
    print("\n=== RENDER API TEST ===")
    r = requests.post(f"{RENDER}/api/info", json={"url": url, "cookies": {"mode": "none"}}, timeout=120)
    print("info status", r.status_code)
    if r.status_code != 200:
        print(r.text[:500])
        return
    info = r.json()
    print("formats:", info.get("formats"))
    fmt_id = (info.get("formats") or [{}])[0].get("id")
    r2 = requests.post(
        f"{RENDER}/api/download",
        json={"url": url, "format": "video", "format_id": fmt_id, "cookies": {"mode": "none"}},
        timeout=60,
    )
    print("download status", r2.status_code, r2.text)
    job_id = r2.json().get("job_id")
    if not job_id:
        return
    for _ in range(90):
        time.sleep(2)
        s = requests.get(f"{RENDER}/api/status/{job_id}", timeout=30).json()
        print("status:", s.get("status"), "progress:", s.get("progress"), "error:", s.get("error"))
        if s.get("status") in ("done", "error"):
            break
    if s.get("status") == "done":
        out = os.path.join(tempfile.gettempdir(), f"render_{job_id}.mp4")
        with requests.get(f"{RENDER}/api/file/{job_id}", stream=True, timeout=120) as fr:
            with open(out, "wb") as fh:
                for chunk in fr.iter_content(65536):
                    fh.write(chunk)
        print("downloaded", out, "size", os.path.getsize(out))
        print("audio check:", ffprobe_audio(out))


if __name__ == "__main__":
    url = TEST_URL
    print("URL:", url)
    try:
        info = list_formats(url)
    except Exception as e:
        print("local format list failed:", e)
        info = None

    if info and info.get("formats"):
        fmt_id = info["formats"][-1].get("format_id")
        for label, fmt in [
            ("best", "best[ext=mp4][acodec!=none]/best[ext=mp4]/best"),
            ("bestvideo+bestaudio", "bestvideo+bestaudio/best[ext=mp4]/best"),
            ("format_id merge", f"{fmt_id}+bestaudio/best[ext=mp4]/best"),
            ("format_id only", str(fmt_id)),
        ]:
            outdir = tempfile.mkdtemp(prefix="reclip_test_")
            try:
                print(f"\n=== LOCAL DOWNLOAD: {label} ===")
                print("format:", fmt)
                files = try_download(url, fmt, outdir)
                for f in files:
                    print(os.path.basename(f), os.path.getsize(f), ffprobe_audio(f))
            except Exception as e:
                print("FAILED:", e)
            finally:
                shutil.rmtree(outdir, ignore_errors=True)

    test_render(url)
