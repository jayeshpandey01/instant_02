import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.downloader import find_matching_cookie_file
from src.routes.api import _resolve_direct_url_via_ytdlp

url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
cookie_path = find_matching_cookie_file(url)
print("Found cookie path:", cookie_path)
direct_url, filename = _resolve_direct_url_via_ytdlp(url, cookie_path)
print("Direct URL:", direct_url[:100] if direct_url else None)
print("Filename:", filename)
