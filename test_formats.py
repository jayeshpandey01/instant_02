import json
import os
import shutil
import subprocess
import sys
import tempfile

import yt_dlp

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.instagram.com/reel/DVn-vNTCIfX/"
COOKIE = os.path.join(os.path.dirname(__file__), "www.instagram.com_cookies.txt")


def probe(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=codec_name", "-of", "json", path,
        ],
        capture_output=True,
        text=True,
    )
    return len(json.loads(result.stdout or "{}").get("streams", []))


def main():
    opts_base = {
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    if os.path.exists(COOKIE):
        opts_base["cookiefile"] = COOKIE

    with yt_dlp.YoutubeDL({**opts_base, "skip_download": True}) as ydl:
        info = ydl.extract_info(URL, download=False)

    print("formats:")
    for fmt in info.get("formats", []):
        print(
            f"  {fmt.get('format_id')} ext={fmt.get('ext')} "
            f"{fmt.get('height')}p v={fmt.get('vcodec')} a={fmt.get('acodec')}"
        )

    tests = [
        "best[ext=mp4]/best",
        "782695861119940v-2",
        "782695861119940v-2+bestaudio/best",
        "bestvideo+bestaudio/best",
        "dash-782695861119940v+dash-739152525796294a/best",
        "dash-782695861119940v+bestaudio/best",
    ]

    for fmt in tests:
        outdir = tempfile.mkdtemp()
        opts = {
            **opts_base,
            "format": fmt,
            "outtmpl": os.path.join(outdir, "t.%(ext)s"),
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(URL, download=True)
            for name in os.listdir(outdir):
                path = os.path.join(outdir, name)
                print(
                    fmt, "->", name, os.path.getsize(path),
                    "audio", probe(path),
                )
        except Exception as exc:
            print(fmt, "FAIL", str(exc)[:160])
        finally:
            shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    main()
