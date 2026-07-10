import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch, mock_open
import src.downloader


@pytest.fixture
def clean_downloader_dirs():
    # Make sure mock directories are set and empty
    orig_user_dir = src.downloader.USER_DIR
    orig_download_dir = src.downloader.DOWNLOAD_DIR
    
    tmp_user = tempfile.mkdtemp()
    tmp_download = tempfile.mkdtemp()
    
    src.downloader.USER_DIR = tmp_user
    src.downloader.DOWNLOAD_DIR = tmp_download
    
    yield tmp_user, tmp_download
    
    shutil.rmtree(tmp_user, ignore_errors=True)
    shutil.rmtree(tmp_download, ignore_errors=True)
    src.downloader.USER_DIR = orig_user_dir
    src.downloader.DOWNLOAD_DIR = orig_download_dir


def test_detect_media_type():
    # None info -> video
    assert src.downloader.detect_media_type(None) == "video"
    
    # Entries of type playlist, all images -> image
    info_image = {
        "_type": "playlist",
        "entries": [
            {"ext": "jpg"},
            {"ext": "png", "url": None, "thumbnail": "some_thumb"}
        ]
    }
    assert src.downloader.detect_media_type(info_image) == "image"
    
    # Audio-only (no video codec, yes audio codec)
    info_audio = {
        "formats": [
            {"ext": "m4a", "vcodec": "none", "acodec": "aac"}
        ]
    }
    assert src.downloader.detect_media_type(info_audio) == "audio_only"
    
    # Video (has video codec)
    info_video = {
        "formats": [
            {"ext": "mp4", "vcodec": "h264", "acodec": "aac"}
        ]
    }
    assert src.downloader.detect_media_type(info_video) == "video"


def test_make_friendly_error():
    assert "configure valid cookies" in src.downloader.make_friendly_error("404 Not Found", "instagram.com")
    assert "verify the URL" in src.downloader.make_friendly_error("404 Not Found", "youtube.com")
    assert "Forbidden" in src.downloader.make_friendly_error("403 Forbidden", "youtube.com")
    assert "Authentication / Bot verification required" in src.downloader.make_friendly_error("confirm you are not a bot", "youtube.com")
    assert "some random error" == src.downloader.make_friendly_error("some random error", "other.com")


def test_needs_transcoding():
    # Non-mp4/m4v/mov extension needs transcoding
    assert src.downloader.needs_transcoding("video.mkv") is True
    
    # MP4 with standard codecs doesn't need transcoding
    with patch("src.downloader.get_video_codecs", return_value=("h264", "aac")), \
         patch("src.downloader.has_video_stream", return_value=True), \
         patch("src.downloader.has_audio_stream", return_value=True):
        assert src.downloader.needs_transcoding("video.mp4") is False
        
    # MP4 with incompatible video codec needs transcoding (e.g. vp9)
    with patch("src.downloader.get_video_codecs", return_value=("vp9", "aac")), \
         patch("src.downloader.has_video_stream", return_value=True), \
         patch("src.downloader.has_audio_stream", return_value=True):
        assert src.downloader.needs_transcoding("video.mp4") is True

    # MP4 with incompatible audio codec needs transcoding (e.g. opus)
    with patch("src.downloader.get_video_codecs", return_value=("h264", "opus")), \
         patch("src.downloader.has_video_stream", return_value=True), \
         patch("src.downloader.has_audio_stream", return_value=True):
        assert src.downloader.needs_transcoding("video.mp4") is True


def test_safe_remove():
    with patch("os.path.exists", return_value=True), \
         patch("os.remove") as mock_remove:
        assert src.downloader.safe_remove("dummy_path") is True
        mock_remove.assert_called_once_with("dummy_path")
        
    # Test retry on OSError
    with patch("os.path.exists", return_value=True), \
         patch("os.remove", side_effect=OSError("locked")), \
         patch("time.sleep") as mock_sleep:
        assert src.downloader.safe_remove("dummy_path", retries=3) is False
        assert mock_sleep.call_count == 3


def test_safe_rename():
    with patch("os.path.exists", return_value=False), \
         patch("os.rename") as mock_rename:
        assert src.downloader.safe_rename("src", "dest") is True
        mock_rename.assert_called_once_with("src", "dest")

    # Cross-device rename fallback (Errno 18)
    with patch("os.path.exists", return_value=False), \
         patch("os.rename", side_effect=OSError(18, "Cross-device link")), \
         patch("shutil.move") as mock_move:
        assert src.downloader.safe_rename("src", "dest") is True
        mock_move.assert_called_once_with("src", "dest")


def test_get_cookie_opts(clean_downloader_dirs):
    user_dir, _ = clean_downloader_dirs
    
    # None cookies
    opts, path = src.downloader.get_cookie_opts(None)
    assert opts == {}
    assert path is None
    
    # Browser mode
    opts, path = src.downloader.get_cookie_opts({"mode": "browser", "browser": "chrome"})
    assert opts == {"cookiesfrombrowser": ("chrome",)}
    assert path is None
    
    # Local file mode (missing)
    with pytest.raises(FileNotFoundError):
        src.downloader.get_cookie_opts({"mode": "local_file", "filename": "missing.txt"})
        
    # Local file mode (exists)
    cookie_file = os.path.join(user_dir, "test_cookie.txt")
    with open(cookie_file, "w") as f:
        f.write("# Netscape HTTP Cookie File")
    opts, path = src.downloader.get_cookie_opts({"mode": "local_file", "filename": "test_cookie.txt"})
    assert opts == {"cookiefile": cookie_file}
    assert path is None

    # Text mode Netscape
    opts, path = src.downloader.get_cookie_opts({"mode": "text", "text": "# Netscape HTTP Cookie File\nfoo\tbar"})
    assert "cookiefile" in opts
    assert path is not None
    assert os.path.exists(path)
    os.remove(path)

    # Text mode header
    opts, path = src.downloader.get_cookie_opts({"mode": "text", "text": "foo=bar; baz=qux"}, url="https://instagram.com")
    assert "cookiefile" in opts
    assert path is not None
    with open(path, "r") as f:
        content = f.read()
        assert ".instagram.com" in content
        assert "foo" in content
        assert "bar" in content
    os.remove(path)


def test_find_matching_cookie_file(clean_downloader_dirs):
    user_dir, _ = clean_downloader_dirs
    
    # None URL
    assert src.downloader.find_matching_cookie_file(None) is None
    
    # Env var match
    with patch.dict(os.environ, {"YOUTUBE_COOKIES": "youtube_cookie_data"}):
        path = src.downloader.find_matching_cookie_file("https://youtube.com/watch?v=123")
        assert path is not None
        assert os.path.exists(path)
        with open(path, "r") as f:
            assert f.read() == "youtube_cookie_data"
        os.remove(path)
        
    # Directory match
    cookie_path = os.path.join(user_dir, "youtube_cookies.txt")
    with open(cookie_path, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
    assert src.downloader.find_matching_cookie_file("https://youtube.com/watch?v=123") == cookie_path


def test_ensure_ffmpeg():
    # Test cases for system ffmpeg present
    with patch("shutil.which", side_effect=lambda x: "/usr/bin/" + x if x in ["ffmpeg", "ffprobe"] else None):
        assert src.downloader.ensure_ffmpeg() == "/usr/bin/ffmpeg"

    # Test cases when download is triggered (system ffmpeg missing)
    with patch("shutil.which", return_value=None), \
         patch("os.path.exists", return_value=True), \
         patch("os.access", return_value=True):
        # Already downloaded in tmp_bin
        assert src.downloader.ensure_ffmpeg().endswith("ffmpeg") or src.downloader.ensure_ffmpeg().endswith("ffmpeg.exe")


def test_convert_to_ios_compatible_mp4():
    # Ensure it returns input path early if ffmpeg is missing
    with patch("src.downloader.ensure_ffmpeg", return_value=None), \
         patch("shutil.which", return_value=None):
        assert src.downloader.convert_to_ios_compatible_mp4("some_video.mp4") == "some_video.mp4"

    # Test run command invocation on transcoding needed
    with patch("src.downloader.ensure_ffmpeg", return_value="/bin/ffmpeg"), \
         patch("os.path.isfile", return_value=True), \
         patch("src.downloader.needs_transcoding", return_value=True), \
         patch("src.downloader.has_audio_stream", side_effect=[True, True]), \
         patch("src.downloader.get_video_codecs", return_value=("h264", "aac")), \
         patch("src.downloader.has_video_stream", return_value=True), \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=100), \
         patch("subprocess.run") as mock_run, \
         patch("src.downloader.safe_remove") as mock_remove, \
         patch("src.downloader.safe_rename", return_value=True) as mock_rename:
        
        path = src.downloader.convert_to_ios_compatible_mp4("video.mov")
        assert mock_run.call_count == 1
        assert mock_rename.call_count == 1


def test_resolve_instagram_video_format():
    info = {
        "formats": [
            {"format_id": "dash-123v", "vcodec": "h264", "acodec": "none", "height": 720},
            {"format_id": "dash-456a", "vcodec": "none", "acodec": "aac", "abr": 128},
            {"format_id": "progressive-789", "vcodec": "h264", "acodec": "aac", "height": 360}
        ]
    }
    # Pick DASH pair
    assert src.downloader.resolve_instagram_video_format(info) == "dash-123v+dash-456a"
    # With height constraint
    assert src.downloader.resolve_instagram_video_format(info, height=480) == "dash-123v+dash-456a"
    # Pick progressive format_id + safety bestaudio
    assert src.downloader.resolve_instagram_video_format(info, format_id="progressive-789") == "progressive-789+bestaudio/best"
    # No formats fallback
    assert src.downloader.resolve_instagram_video_format(None) == "bestvideo+bestaudio/best"


def test_build_video_format_string():
    # Without ffmpeg
    assert src.downloader.build_video_format_string(has_ffmpeg=False) == "best[ext=mp4]/best"
    # With info
    info = {
        "formats": [
            {"format_id": "dash-12v", "vcodec": "h264", "acodec": "none"},
            {"format_id": "dash-34a", "vcodec": "none", "acodec": "aac"}
        ]
    }
    assert src.downloader.build_video_format_string(info=info) == "dash-12v+dash-34a"
    # With format_id
    assert src.downloader.build_video_format_string(format_id="137") == "137+bestaudio/best"
    # Default
    assert src.downloader.build_video_format_string() == "bestvideo+bestaudio/best"


def test_run_ytdlp_with_fallback(clean_downloader_dirs):
    user_dir, _ = clean_downloader_dirs
    # Mock YoutubeDL to succeed — must handle context manager (with ... as ydl:)
    mock_ydl_instance = MagicMock()
    mock_ydl_instance.extract_info.return_value = {"title": "Success Video"}
    mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
    mock_ydl_instance.__exit__ = MagicMock(return_value=False)

    with patch("yt_dlp.YoutubeDL", return_value=mock_ydl_instance):
        info, cookie_file, fallback, err = src.downloader.run_ytdlp_with_fallback({}, "http://example.com", {"mode": "none"})
        assert info == {"title": "Success Video"}
        assert cookie_file is None
        assert fallback is False
        assert err is None

    # Mock YoutubeDL to fail, trigger fallback to no cookies
    mock_ydl_fail = MagicMock()
    mock_ydl_fail.extract_info.side_effect = Exception("HTTP Error 403")
    mock_ydl_fail.__enter__ = MagicMock(return_value=mock_ydl_fail)
    mock_ydl_fail.__exit__ = MagicMock(return_value=False)

    mock_ydl_success_no_cookies = MagicMock()
    mock_ydl_success_no_cookies.extract_info.return_value = {"title": "No Cookies Success"}
    mock_ydl_success_no_cookies.__enter__ = MagicMock(return_value=mock_ydl_success_no_cookies)
    mock_ydl_success_no_cookies.__exit__ = MagicMock(return_value=False)

    with patch("yt_dlp.YoutubeDL", side_effect=[mock_ydl_fail, mock_ydl_success_no_cookies]):
        info, cookie_file, fallback, err = src.downloader.run_ytdlp_with_fallback({}, "http://example.com", {"mode": "browser", "browser": "chrome"})
        assert info == {"title": "No Cookies Success"}
        assert cookie_file is None
        assert fallback is False
        assert err is None


def test_collect_download_files(clean_downloader_dirs):
    user_dir, download_dir = clean_downloader_dirs
    job_id = "testjob123"
    
    fragment_file = os.path.join(download_dir, f"{job_id}.f137.mp4")
    video_file = os.path.join(download_dir, f"{job_id}_main.mp4")
    audio_file = os.path.join(download_dir, f"{job_id}_audio.m4a")
    
    for f in [fragment_file, video_file, audio_file]:
        with open(f, "w") as fp:
            fp.write("dummy content")

    with patch("src.downloader.has_video_stream", side_effect=lambda x: x.endswith(".mp4")):
        # Filter for video choice
        video_files = src.downloader.collect_download_files(job_id, "video")
        assert video_file in video_files
        assert fragment_file not in video_files
        assert audio_file not in video_files
        
        # Filter for audio choice
        audio_files = src.downloader.collect_download_files(job_id, "audio")
        assert audio_file in audio_files
        assert video_file not in audio_files


def test_manual_merge_video_audio(clean_downloader_dirs):
    user_dir, download_dir = clean_downloader_dirs
    v_path = os.path.join(download_dir, "video.mp4")
    a_path = os.path.join(download_dir, "audio.m4a")
    merged_path = os.path.join(download_dir, "video_merged.mp4")
    
    with open(v_path, "w") as f: f.write("v")
    with open(a_path, "w") as f: f.write("a")
    
    def create_merged_file(*args, **kwargs):
        with open(merged_path, "w") as f: f.write("merged")
        return MagicMock(returncode=0)

    with patch("src.downloader.ensure_ffmpeg", return_value="ffmpeg"), \
         patch("subprocess.run", side_effect=create_merged_file), \
         patch("src.downloader._ffprobe_streams", return_value=True), \
         patch("os.path.getsize", return_value=10):
        
        res = src.downloader.manual_merge_video_audio(v_path, a_path)
        assert res == merged_path
        assert os.path.exists(merged_path)


def test_finalize_video_files(clean_downloader_dirs):
    user_dir, download_dir = clean_downloader_dirs
    v_path = os.path.join(download_dir, "video.mp4")
    a_path = os.path.join(download_dir, "audio.m4a")
    with open(v_path, "w") as f: f.write("v")
    with open(a_path, "w") as f: f.write("a")
    
    # Case 1: Video already has audio stream
    with patch("src.downloader.has_audio_stream", return_value=True):
        res = src.downloader.finalize_video_files("job1", [v_path])
        assert res == [v_path]

    # Case 2: Video has no audio stream, companion found, merge succeeds
    with patch("src.downloader.has_audio_stream", return_value=False), \
         patch("src.downloader._find_audio_companion", return_value=a_path), \
         patch("src.downloader.manual_merge_video_audio", return_value="merged.mp4"):
        res = src.downloader.finalize_video_files("job1", [v_path])
        assert res == ["merged.mp4"]


def test_ensure_video_has_audio(clean_downloader_dirs):
    user_dir, download_dir = clean_downloader_dirs
    v_path = os.path.join(download_dir, "video.mp4")
    with open(v_path, "w") as f: f.write("v")
    
    # Case 1: Already has audio
    with patch("src.downloader.finalize_video_files", return_value=[v_path]), \
         patch("src.downloader.collect_download_files", return_value=[v_path]), \
         patch("src.downloader.has_audio_stream", return_value=True):
        info, files, err = src.downloader.ensure_video_has_audio("job1", "http://url", {}, {})
        assert files == [v_path]
        assert err is None
