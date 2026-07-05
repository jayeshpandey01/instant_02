import os

# 1. Update src/downloader.py
with open("src/downloader.py", "a", encoding="utf-8") as f:
    f.write('''
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
        for fmt in item.get("formats", []):
            ext = (fmt.get("ext") or "").lower()
            vcodec = (fmt.get("vcodec") or "none").lower()
            acodec = (fmt.get("acodec") or "none").lower()
            if ext in IMAGE_EXTENSIONS: is_item_image = True
            if vcodec != "none":
                has_video = True
                all_images = False
            if acodec != "none": has_audio = True
        if not item.get("formats"):
            ext = (item.get("ext") or "").lower()
            if ext in IMAGE_EXTENSIONS: is_item_image = True
            else: all_images = False
    if all_images and not has_video: return "image"
    if not has_video and has_audio: return "audio_only"
    return "video"
''')

with open("src/downloader.py", "r", encoding="utf-8") as f:
    dl_content = f.read()
dl_content = dl_content.replace('ydl_opts = {**ydl_opts_base, **cookie_opts}', 'ydl_opts = {**ydl_opts_base, **cookie_opts, "logger": SilentLogger()}')
with open("src/downloader.py", "w", encoding="utf-8") as f:
    f.write(dl_content)


# 2. Update src/routes/api.py
with open("src/routes/api.py", "r", encoding="utf-8") as f:
    api_content = f.read()

get_info_replacement = '''
    media_type = detect_media_type(info)
    title = info.get("title", "Unknown Title")
    
    return jsonify({
        "status": "success",
        "title": title,
        "media_type": media_type,
        "formats": formats
    })
'''
api_content = api_content.replace('''    title = info.get("title", "Unknown Title")
    
    return jsonify({
        "status": "success",
        "title": title,
        "formats": formats
    })''', get_info_replacement)

# also fix imports
if 'detect_media_type' not in api_content:
    api_content = api_content.replace('from src.downloader import run_ytdlp_with_fallback', 'from src.downloader import run_ytdlp_with_fallback, detect_media_type')

with open("src/routes/api.py", "w", encoding="utf-8") as f:
    f.write(api_content)


# 3. Update src/tasks.py
with open("src/tasks.py", "r", encoding="utf-8") as f:
    tasks_content = f.read()

image_logic = '''
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
    url_ext = direct.split("?")[0].rsplit(".", 1)[-1].lower()
    if direct:
        return direct, url_ext if url_ext in IMAGE_EXTENSIONS else "jpg"
    return None, "jpg"

'''

if "get_image_url_from_entry" not in tasks_content:
    tasks_content = tasks_content.replace('def run_download', image_logic + 'def run_download')

# replace format_choice == "audio" with image handler
new_image_handler = '''
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
                job["error"] = err.split("\\n")[-1]
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
            
        if format_choice == "audio":
'''
tasks_content = tasks_content.replace('        if format_choice == "audio":', new_image_handler)


mixed_carousel_handler = '''
        if fallback:
            job["fallback_used"] = used_cookie

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

        # Find all files starting with job_id
'''
tasks_content = tasks_content.replace('''        if fallback:
            job["fallback_used"] = used_cookie

        # Find all files starting with job_id''', mixed_carousel_handler)

with open("src/tasks.py", "w", encoding="utf-8") as f:
    f.write(tasks_content)

print("Patch complete.")
