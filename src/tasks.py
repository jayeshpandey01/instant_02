import os
import time
import glob
import shutil
import re
from src.config import DOWNLOAD_DIR
from src.downloader import (
    run_ytdlp_with_fallback,
    convert_to_ios_compatible_mp4,
    ensure_ffmpeg,
    resolve_instagram_video_format,
    get_format_height,
    prefetch_video_info,
    ensure_video_has_audio,
    collect_download_files,
)


import json

class TrackedDict(dict):
    def __init__(self, data, save_callback):
        super().__init__(data)
        self._save_callback = save_callback
        
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._save_callback(self)
        
    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._save_callback(self)
        
    def pop(self, *args, **kwargs):
        val = super().pop(*args, **kwargs)
        self._save_callback(self)
        return val

class PersistentJobs:
    def _get_conn(self):
        from src.database import get_db_connection
        return get_db_connection()
        
    def _save(self, key, data):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO jobs (id, data) VALUES (?, ?)", (key, json.dumps(data)))
        conn.commit()
        conn.close()
        
    def __getitem__(self, key):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT data FROM jobs WHERE id = ?", (key,))
        row = cur.fetchone()
        conn.close()
        if not row:
            raise KeyError(key)
        
        def save_callback(d):
            self._save(key, d)
            
        return TrackedDict(json.loads(row[0]), save_callback)
        
    def __setitem__(self, key, value):
        self._save(key, value)
        
    def __contains__(self, key):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM jobs WHERE id = ?", (key,))
        row = cur.fetchone()
        conn.close()
        return row is not None
        
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
            
    def pop(self, key, default=None):
        try:
            val = self[key]
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM jobs WHERE id = ?", (key,))
            conn.commit()
            conn.close()
            return val
        except KeyError:
            return default

    def items(self):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, data FROM jobs")
        rows = cur.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            key = row[0]
            def save_callback(d, k=key):
                self._save(k, d)
            results.append((key, TrackedDict(json.loads(row[1]), save_callback)))
        return results

jobs = PersistentJobs()

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


def get_image_url_from_entry(entry):
    from src.downloader import IMAGE_EXTENSIONS
    if not entry:
        return None
    for fmt in sorted(entry.get("formats", []), key=lambda f: f.get("width") or 0, reverse=True):
        ext = (fmt.get("ext") or "").lower()
        if ext in IMAGE_EXTENSIONS:
            return fmt.get("url"), ext
        vcodec = (fmt.get("vcodec") or "none").lower()
        acodec = (fmt.get("acodec") or "none").lower()
        if vcodec == "none" and acodec == "none" and fmt.get("url"):
            u = fmt["url"]
            url_ext = u.split("?")[0].rsplit(".", 1)[-1].lower()
            if url_ext in IMAGE_EXTENSIONS:
                return u, url_ext
    direct = entry.get("url") or ""
    if not direct:
        thumbnails = entry.get("thumbnails", [])
        if thumbnails:
            direct = thumbnails[-1].get("url", "")
        if not direct:
            direct = entry.get("thumbnail", "")
    
    url_ext = direct.split("?")[0].rsplit(".", 1)[-1].lower() if direct else ""
    if direct:
        return direct, url_ext if url_ext in IMAGE_EXTENSIONS else "jpg"
    return None, "jpg"
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

        ensure_ffmpeg()
        has_ffmpeg = shutil.which("ffmpeg") is not None

        if format_choice == "image":
            info_opts = {
                "noplaylist": False,
                "quiet": True,
                "no_warnings": True,
                "ignore_no_formats_error": True,
            }
            info, used_cookie, fallback, err = run_ytdlp_with_fallback(info_opts, url, cookies_data, download=False)
            if err:
                job["status"] = "error"
                job["error"] = err.split("\n")[-1]
                return
            if fallback:
                job["fallback_used"] = used_cookie

            import requests as req_lib
            entries = info.get("entries", []) if (info.get("_type") == "playlist" or "entries" in info) else None
            
            image_targets = []
            if entries:
                for entry in entries:
                    img_url, img_ext = get_image_url_from_entry(entry)
                    if img_url:
                        image_targets.append((img_url, img_ext))
            else:
                img_url, img_ext = get_image_url_from_entry(info)
                if img_url:
                    image_targets.append((img_url, img_ext))

            if not image_targets:
                job["status"] = "error"
                job["error"] = "Could not find a downloadable image URL"
                return

            headers = {"User-Agent": "Mozilla/5.0"}
            downloaded_files = []
            for i, (img_url, img_ext) in enumerate(image_targets):
                out_path = os.path.join(DOWNLOAD_DIR, f"{job_id}_{i+1}.{img_ext}")
                try:
                    resp = req_lib.get(img_url, headers=headers, timeout=30, stream=True)
                    resp.raise_for_status()
                    with open(out_path, "wb") as fh:
                        for chunk in resp.iter_content(8192):
                            fh.write(chunk)
                    downloaded_files.append(out_path)
                    job["progress"] = int((i + 1) / len(image_targets) * 100)
                except Exception as dl_err:
                    job["status"] = "error"
                    job["error"] = f"Image download failed: {dl_err}"
                    return

            if not downloaded_files:
                job["status"] = "error"
                job["error"] = "No images were downloaded"
                return

            if len(downloaded_files) > 1:
                import zipfile
                zip_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.zip")
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for idx_f, fp in enumerate(downloaded_files):
                        ext_f = os.path.splitext(fp)[1]
                        zf.write(fp, f"Image_{idx_f+1}{ext_f}")
                for fp in downloaded_files:
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
                chosen = zip_path
                ext = ".zip"
            else:
                chosen = downloaded_files[0]
                ext = os.path.splitext(chosen)[1]

            job["status"] = "done"
            job["file"] = chosen
            title = info.get("title", "").strip() or job.get("title", "").strip()
            job["filename"] = f"{(title[:20].strip() or os.path.basename(chosen))}{ext}"
            return
            
        meta = None
        if format_choice == "audio":

            ydl_opts_base["format"] = "bestaudio/best"
            if has_ffmpeg:
                ydl_opts_base["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            info, used_cookie, fallback, err = run_ytdlp_with_fallback(ydl_opts_base, url, cookies_data, download=True)
        else:
            meta, used_cookie, fallback, err = prefetch_video_info(url, cookies_data)
            if err:
                job["status"] = "error"
                job["error"] = err.split("\n")[-1]
                return
            if fallback:
                job["fallback_used"] = used_cookie

            selected_height = get_format_height(meta, format_id)
            ydl_opts_base["format"] = resolve_instagram_video_format(
                meta,
                format_id=format_id,
                height=selected_height,
            )
            if has_ffmpeg:
                ydl_opts_base["merge_output_format"] = "mp4"

            info, used_cookie, fallback, err = run_ytdlp_with_fallback(ydl_opts_base, url, cookies_data, download=True)

        if err:
            job["status"] = "error"
            job["error"] = err.split("\n")[-1]
            return

        if fallback:
            job["fallback_used"] = used_cookie

        if format_choice not in ("audio", "image"):
            info, files, audio_err = ensure_video_has_audio(
                job_id,
                url,
                cookies_data,
                ydl_opts_base,
                info=info or meta,
                format_id=format_id,
                height=get_format_height(info or meta, format_id),
            )
            if audio_err:
                job["status"] = "error"
                job["error"] = audio_err.split("\n")[-1]
                return
        else:
            files = collect_download_files(job_id, format_choice)

        # ---------------------------------------------------------
        # SUPPLEMENTAL IMAGE DOWNLOAD FOR MIXED CAROUSELS
        # ---------------------------------------------------------
        if info and (info.get("_type") == "playlist" or "entries" in info):
            entries = info.get("entries", [])
            import requests as req_lib
            headers = {"User-Agent": "Mozilla/5.0"}
            for i, entry in enumerate(entries):
                if entry:
                    is_image_only = True
                    for fmt in entry.get("formats", []):
                        if fmt.get("vcodec", "none").lower() != "none" or fmt.get("acodec", "none").lower() != "none":
                            is_image_only = False
                            break
                    if is_image_only:
                        img_url, img_ext = get_image_url_from_entry(entry)
                        if img_url:
                            out_path = os.path.join(DOWNLOAD_DIR, f"{job_id}_img_{i+1}.{img_ext}")
                            try:
                                resp = req_lib.get(img_url, headers=headers, timeout=30, stream=True)
                                if resp.status_code == 200:
                                    with open(out_path, "wb") as fh:
                                        for chunk in resp.iter_content(8192):
                                            fh.write(chunk)
                            except Exception:
                                pass

        if format_choice in ("audio", "image"):
            files = collect_download_files(job_id, format_choice)
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
                # Transcode files to iOS compatible format before zipping
                if format_choice != "audio":
                    job["status"] = "converting"
                    files = [convert_to_ios_compatible_mp4(f) for f in files]
                
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
            if format_choice != "audio":
                job["status"] = "converting"
                chosen = convert_to_ios_compatible_mp4(chosen)
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

