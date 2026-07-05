import os
import re
import shutil
import tempfile
import time
import urllib.request
import zipfile
import subprocess
import yt_dlp
import glob
from urllib.parse import urlparse
from src.config import BASE_DIR, DOWNLOAD_DIR

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".3gp", ".avi"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".opus", ".wav", ".ogg"}


def ensure_ffmpeg():
    import shutil
    import sys
    import urllib.request
    import zipfile
    
    tmp_bin = "/tmp/bin"
    
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        # System ffmpeg exists — also ensure ffprobe is available
        if not shutil.which("ffprobe") and sys.platform.startswith("linux"):
            _download_ffprobe(tmp_bin)
        return system_ffmpeg
        
    if not sys.platform.startswith("linux"):
        return None
        
    ffmpeg_path = os.path.join(tmp_bin, "ffmpeg")
    ffprobe_path = os.path.join(tmp_bin, "ffprobe")
    
    # Check if both already downloaded
    if os.path.exists(ffmpeg_path) and os.access(ffmpeg_path, os.X_OK):
        if tmp_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = tmp_bin + os.pathsep + os.environ.get("PATH", "")
        # Still ensure ffprobe is there
        if not os.path.exists(ffprobe_path) or not os.access(ffprobe_path, os.X_OK):
            _download_ffprobe(tmp_bin)
        return ffmpeg_path
        
    os.makedirs(tmp_bin, exist_ok=True)
    
    # Download ffmpeg
    zip_path = os.path.join(tmp_bin, "ffmpeg.zip")
    url = "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-linux-64.zip"
    
    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_bin)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        os.chmod(ffmpeg_path, 0o755)
        
        if tmp_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = tmp_bin + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        print(f"Error downloading ffmpeg: {e}")
        return None
    
    # Download ffprobe (separate zip on ffbinaries)
    _download_ffprobe(tmp_bin)
    
    return ffmpeg_path


def _download_ffprobe(tmp_bin):
    """Download ffprobe binary from ffbinaries (packaged separately from ffmpeg)."""
    import urllib.request
    import zipfile
    
    ffprobe_path = os.path.join(tmp_bin, "ffprobe")
    if os.path.exists(ffprobe_path) and os.access(ffprobe_path, os.X_OK):
        return ffprobe_path
    
    os.makedirs(tmp_bin, exist_ok=True)
    zip_path = os.path.join(tmp_bin, "ffprobe.zip")
    url = "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffprobe-4.4.1-linux-64.zip"
    
    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_bin)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        os.chmod(ffprobe_path, 0o755)
        
        if tmp_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = tmp_bin + os.pathsep + os.environ.get("PATH", "")
        
        print(f"ffprobe downloaded successfully to {ffprobe_path}")
        return ffprobe_path
    except Exception as e:
        print(f"Error downloading ffprobe: {e}")
        return None

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
            file_path = os.path.join(BASE_DIR, safe_name)
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
        
        root_dir = BASE_DIR
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
    Runs a native yt-dlp operation. If mode is "none", it proactively checks if a local matching
    cookie file exists in BASE_DIR and uses it. If that fails or isn't found, it falls back normally.
    Returns (info_dict_or_none, used_cookie_file, fallback_activated, error_msg_or_none)
    """
    mode = cookies_data.get("mode", "none") if cookies_data else "none"
    
    cookie_opts = {}
    temp_cookie_file = None
    fallback_activated = False
    used_cookie_file = None
    
    if mode == "none":
        # Proactively check if we have a matching local cookie file in BASE_DIR
        local_cookie_path = find_matching_cookie_file(url)
        if local_cookie_path:
            cookie_path_to_use = local_cookie_path
            if os.environ.get("VERCEL"):
                import shutil
                temp_cleanup_path = os.path.join("/tmp", os.path.basename(local_cookie_path))
                try:
                    shutil.copy2(local_cookie_path, temp_cleanup_path)
                    cookie_path_to_use = temp_cleanup_path
                    temp_cookie_file = temp_cleanup_path
                except Exception:
                    pass
            cookie_opts = {"cookiefile": cookie_path_to_use}
            used_cookie_file = local_cookie_path
            fallback_activated = True
    else:
        cookie_opts, temp_cookie_file = get_cookie_opts(cookies_data, url)
        if temp_cookie_file:
            used_cookie_file = temp_cookie_file
        elif cookie_opts.get("cookiefile"):
            used_cookie_file = cookie_opts["cookiefile"]
            
    logger_to_use = ydl_opts_base.get("logger") or SilentLogger()
    ydl_opts = augment_ytdlp_opts({**ydl_opts_base, **cookie_opts, "logger": logger_to_use})
    
    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=download)
                return info, os.path.basename(used_cookie_file) if used_cookie_file else None, fallback_activated, None
        except Exception as e:
            error_msg = str(e)
            
            needs_auth = (
                "sign in" in error_msg.lower() or
                "login" in error_msg.lower() or
                "empty media response" in error_msg.lower() or
                "confirm you are not a bot" in error_msg.lower() or
                "private video" in error_msg.lower() or
                "private" in error_msg.lower() or
                "unreachable" in error_msg.lower() or
                "http error 403" in error_msg.lower() or
                "members-only" in error_msg.lower()
            )
            
            # If we didn't already try with a local cookie file, and we need auth, try it now
            if mode == "none" and needs_auth and not cookie_opts.get("cookiefile"):
                local_cookie_path = find_matching_cookie_file(url)
                if local_cookie_path:
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
                    
                    ydl_opts_retry = augment_ytdlp_opts({**ydl_opts_base, "cookiefile": cookie_path_to_use, "logger": logger_to_use})
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts_retry) as ydl_retry:
                            info_retry = ydl_retry.extract_info(url, download=download)
                            return info_retry, os.path.basename(local_cookie_path), True, None
                    except Exception as e_retry:
                        return None, os.path.basename(local_cookie_path), True, str(e_retry)
                    finally:
                        if temp_cleanup_path:
                            try:
                                os.remove(temp_cleanup_path)
                            except OSError:
                                pass
            return None, os.path.basename(used_cookie_file) if used_cookie_file else None, fallback_activated, error_msg
    finally:
        if temp_cookie_file:
            try:
                os.remove(temp_cookie_file)
            except OSError:
                pass

def get_ffprobe_path():
    """Find ffprobe binary, checking system PATH and /tmp/bin fallback."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe
    # Check /tmp/bin (where ensure_ffmpeg downloads it on Linux)
    tmp_ffprobe = "/tmp/bin/ffprobe"
    if os.path.exists(tmp_ffprobe) and os.access(tmp_ffprobe, os.X_OK):
        return tmp_ffprobe
    return None


def get_ffmpeg_location():
    ffmpeg = ensure_ffmpeg() or shutil.which("ffmpeg")
    if not ffmpeg:
        # Direct fallback to /tmp/bin
        tmp_ffmpeg = "/tmp/bin/ffmpeg"
        if os.path.exists(tmp_ffmpeg) and os.access(tmp_ffmpeg, os.X_OK):
            return "/tmp/bin"
        return None
    return os.path.dirname(os.path.abspath(ffmpeg))


def augment_ytdlp_opts(opts):
    """Ensure yt-dlp can locate ffmpeg/ffprobe for merge/post-process steps."""
    ffmpeg_dir = get_ffmpeg_location()
    merged = dict(opts)
    if ffmpeg_dir:
        merged["ffmpeg_location"] = ffmpeg_dir
    return merged


def resolve_instagram_video_format(info, format_id=None, height=None):
    """Build a yt-dlp format selector that preserves Instagram audio."""
    formats = info.get("formats") or [] if info else []

    def fmt_id(fmt):
        return str(fmt.get("format_id") or "")

    def is_progressive(fmt):
        fid = fmt_id(fmt)
        return bool(re.search(r"v-\d+$", fid)) and (fmt.get("acodec") or "none").lower() != "none"

    def is_dash_video(fmt):
        fid = fmt_id(fmt)
        return (
            fid.startswith("dash-")
            and fid.endswith("v")
            and (fmt.get("vcodec") or "none").lower() != "none"
        )

    def is_dash_audio(fmt):
        fid = fmt_id(fmt)
        return (
            fid.startswith("dash-")
            and fid.endswith("a")
            and (fmt.get("acodec") or "none").lower() != "none"
        )

    def pick_dash_pair(video_formats):
        if height:
            matched = [fmt for fmt in video_formats if (fmt.get("height") or 0) <= height]
            video_formats = matched or video_formats
        dash_audios = [fmt for fmt in formats if is_dash_audio(fmt)]
        if not video_formats or not dash_audios:
            return None
        video_fmt = max(video_formats, key=lambda fmt: fmt.get("height") or 0)
        audio_fmt = max(dash_audios, key=lambda fmt: fmt.get("abr") or fmt.get("tbr") or 0)
        return f"{fmt_id(video_fmt)}+{fmt_id(audio_fmt)}"

    if format_id:
        selected = next((fmt for fmt in formats if fmt_id(fmt) == str(format_id)), None)
        if selected:
            if (selected.get("acodec") or "none").lower() != "none":
                return fmt_id(selected)
            if is_dash_video(selected):
                paired = pick_dash_pair([selected])
                if paired:
                    return paired
            return f"{fmt_id(selected)}+bestaudio/best"

    progressive = sorted(
        [fmt for fmt in formats if is_progressive(fmt)],
        key=lambda fmt: fmt.get("height") or 0,
        reverse=True,
    )
    if progressive:
        if height:
            matched = [fmt for fmt in progressive if (fmt.get("height") or 0) <= height]
            progressive = matched or progressive
        return fmt_id(progressive[0])

    dash_videos = [fmt for fmt in formats if is_dash_video(fmt)]
    paired = pick_dash_pair(dash_videos)
    if paired:
        return paired

    return "bestvideo+bestaudio/best"


def build_video_format_string(format_id=None, has_ffmpeg=True, height=None, info=None):
    """Backward-compatible wrapper around Instagram-aware format resolution."""
    if not has_ffmpeg:
        return "best[ext=mp4]/best"

    if info:
        return resolve_instagram_video_format(info, format_id=format_id, height=height)

    if format_id:
        safe_id = str(format_id)
        return f"{safe_id}+bestaudio/best"

    return "bestvideo+bestaudio/best"


def _ffprobe_streams(input_path, stream_type):
    ffprobe = get_ffprobe_path()
    if not ffprobe or not os.path.isfile(input_path):
        return None

    cmd = [
        ffprobe,
        "-v", "error",
        "-select_streams", stream_type,
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        input_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False
        return bool(result.stdout.strip())
    except Exception:
        return None


def has_audio_stream(input_path):
    result = _ffprobe_streams(input_path, "a")
    if result is None:
        # ffprobe unavailable — assume audio exists (optimistic) to avoid
        # discarding valid files or triggering false "no audio" errors
        return True
    return result


def has_video_stream(input_path):
    result = _ffprobe_streams(input_path, "v")
    if result is None:
        return True
    return result


def list_job_media_files(job_id, format_choice):
    pattern = os.path.join(DOWNLOAD_DIR, f"{job_id}*")
    files = [path for path in glob.glob(pattern) if os.path.isfile(path)]
    filtered = []
    for path in files:
        base = os.path.basename(path)
        if base.endswith(".ios.mp4"):
            continue
        if format_choice not in ("image", "audio") and "_img_" in base:
            continue
        filtered.append(path)
    return sorted(filtered)


def collect_download_files(job_id, format_choice):
    """Return final media files for a job, excluding yt-dlp merge fragments."""
    filtered = []
    for path in list_job_media_files(job_id, format_choice):
        base = os.path.basename(path)
        if re.search(r"\.f\d+\.", base):
            continue
        filtered.append(path)

    if not filtered:
        filtered = list_job_media_files(job_id, format_choice)

    merged = [path for path in filtered if os.path.basename(path).endswith("_merged.mp4")]
    if merged:
        filtered = merged

    if format_choice == "audio":
        audio_files = [
            f for f in filtered
            if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS
        ]
        return sorted(audio_files or filtered)

    if format_choice == "image":
        return sorted(filtered)

    video_files = [
        f for f in filtered
        if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS and has_video_stream(f)
    ]
    return sorted(video_files or filtered)


def manual_merge_video_audio(video_path, audio_path):
    ffmpeg = ensure_ffmpeg() or shutil.which("ffmpeg")
    if not ffmpeg or not os.path.isfile(video_path) or not os.path.isfile(audio_path):
        return None

    merged_path = os.path.splitext(video_path)[0] + "_merged.mp4"
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        merged_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=True,
        )
        del result
        if os.path.exists(merged_path) and os.path.getsize(merged_path) > 0:
            # Accept merge result if ffmpeg succeeded. If ffprobe is available,
            # verify audio; if not, trust the merge (ffmpeg exit code 0 = success).
            audio_check = _ffprobe_streams(merged_path, "a")
            if audio_check is None or audio_check:
                return merged_path
            # ffprobe positively says no audio — discard
            print(f"Merge produced file without audio: {merged_path}")
    except Exception as e:
        print(f"FFmpeg merge failed: {e}")
        if os.path.exists(merged_path):
            try:
                os.remove(merged_path)
            except OSError:
                pass
    return None


def _find_audio_companion(job_id, video_path):
    candidates = []
    for path in list_job_media_files(job_id, "video"):
        if path == video_path:
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS and has_audio_stream(path):
            candidates.append(path)
            continue
        if re.search(r"\.f\d+\.", os.path.basename(path)) and has_audio_stream(path) and not has_video_stream(path):
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=os.path.getsize)


def finalize_video_files(job_id, video_paths):
    """Attach audio when yt-dlp saved video/audio separately or merge failed on server."""
    finalized = []
    for video_path in video_paths:
        if has_audio_stream(video_path):
            finalized.append(video_path)
            continue

        audio_path = _find_audio_companion(job_id, video_path)
        if not audio_path:
            finalized.append(video_path)
            continue

        merged_path = manual_merge_video_audio(video_path, audio_path)
        if merged_path:
            for stale in (video_path, audio_path):
                try:
                    if os.path.exists(stale):
                        os.remove(stale)
                except OSError:
                    pass
            finalized.append(merged_path)
        else:
            finalized.append(video_path)

    return finalized


def get_format_height(info, format_id):
    if not info or not format_id:
        return None
    for fmt in info.get("formats") or []:
        if str(fmt.get("format_id")) == str(format_id):
            return fmt.get("height")
    return None


def prefetch_video_info(url, cookies_data):
    info_opts = {
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "ignore_no_formats_error": True,
    }
    return run_ytdlp_with_fallback(info_opts, url, cookies_data, download=False)


def build_instagram_retry_format(info, format_id=None, height=None):
    if format_id:
        return f"{format_id}+bestaudio/best"
    return "bestvideo+bestaudio/best"


def ensure_video_has_audio(job_id, url, cookies_data, ydl_opts_base, info=None, format_id=None, height=None):
    files = finalize_video_files(job_id, collect_download_files(job_id, "video"))
    if files and all(has_audio_stream(path) for path in files):
        return info, files, None

    # If we have files but ffprobe is unavailable, don't discard them — 
    # has_audio_stream already returns True optimistically in that case,
    # so we only reach here when ffprobe positively confirmed no audio.
    # Still, only retry if we actually got files without audio.
    if not files:
        return info, [], "Download completed but no file was found"

    for stale in list_job_media_files(job_id, "video"):
        try:
            os.remove(stale)
        except OSError:
            pass

    retry_opts = augment_ytdlp_opts(dict(ydl_opts_base))
    retry_opts["format"] = build_instagram_retry_format(info, format_id=format_id, height=height)
    retry_opts["merge_output_format"] = "mp4"
    info_retry, _, _, err = run_ytdlp_with_fallback(retry_opts, url, cookies_data, download=True)
    if err:
        return info, [], err

    files = finalize_video_files(job_id, collect_download_files(job_id, "video"))
    if files and all(has_audio_stream(path) for path in files):
        return info_retry or info, files, None

    # Only report "no audio" if ffprobe positively confirmed it (not when ffprobe is missing)
    if files:
        ffprobe_available = get_ffprobe_path() is not None
        if ffprobe_available and not all(has_audio_stream(path) for path in files):
            return info_retry or info, files, "Download completed but the video has no audio track"
        # ffprobe unavailable or check passed — return files as-is
        return info_retry or info, files, None

    return info_retry or info, files, None


def needs_transcoding(input_path):
    import subprocess
    import shutil
    if not shutil.which("ffmpeg"):
        return False
        
    cmd = ["ffmpeg", "-i", input_path]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        stderr = result.stderr.lower()
        
        has_video = "video:" in stderr
        is_h264 = "video: h264" in stderr or "video: avc" in stderr
        
        if has_video and not is_h264:
            return True
            
        has_audio = "audio:" in stderr
        is_compatible_audio = "audio: aac" in stderr or "audio: mp3" in stderr or "audio: mp4a" in stderr
        if has_audio and not is_compatible_audio:
            return True
            
        return False
    except Exception:
        return True

def convert_to_ios_compatible_mp4(input_path):
    import subprocess
    if not shutil.which("ffmpeg"):
        return input_path

    _, ext = os.path.splitext(input_path)
    if ext.lower() not in [".mp4", ".mov", ".m4v", ".webm", ".mkv", ".3gp", ".avi"]:
        return input_path

    target_path = os.path.splitext(input_path)[0] + ".mp4"
    temp_output = input_path + ".ios.mp4"

    if not needs_transcoding(input_path):
        # File is already H.264/AAC — just run a fast stream-copy to add faststart moov atom
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-map", "0:v:0?",
            "-map", "0:a:0?",
            "-c", "copy",
            "-movflags", "+faststart",
            temp_output
        ]
    else:
        # Full transcode to H.264/AAC with faststart
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-map", "0:v:0?",
            "-map", "0:a:0?",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-profile:v", "high",
            "-level", "4.0",
            "-c:a", "aac",
            "-strict", "experimental",
            "-movflags", "+faststart",
            temp_output
        ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
            try:
                os.remove(input_path)
            except OSError:
                pass
            if os.path.exists(target_path) and target_path != temp_output:
                try:
                    os.remove(target_path)
                except OSError:
                    pass
            os.rename(temp_output, target_path)
            return target_path
    except Exception:
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass
    return input_path


IMAGE_EXTENSIONS = {"jpg", "jpeg", "webp", "png", "gif", "avif", "heic"}

class SilentLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

def detect_media_type(info):
    if not info:
        return "video"
    entries = info.get("entries") if info.get("_type") == "playlist" or "entries" in info else None
    items = entries if entries else [info]
    has_video = False
    has_audio = False
    all_images = True
    for item in items:
        if not item: continue
        is_item_image = False
        formats = item.get("formats", [])
        if formats:
            for fmt in formats:
                ext = (fmt.get("ext") or "").lower()
                vcodec = (fmt.get("vcodec") or "none").lower()
                acodec = (fmt.get("acodec") or "none").lower()
                if ext in IMAGE_EXTENSIONS: is_item_image = True
                if vcodec != "none":
                    has_video = True
                    all_images = False
                if acodec != "none": has_audio = True
        else:
            ext = (item.get("ext") or "").lower()
            if ext in IMAGE_EXTENSIONS: 
                is_item_image = True
            elif item.get("url") is None and item.get("thumbnail"):
                is_item_image = True
            else: 
                all_images = False
    if all_images and not has_video: return "image"
    if not has_video and has_audio: return "audio_only"
    return "video"
