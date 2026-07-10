import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.routes.api import _resolve_direct_url_via_ytdlp

url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
direct_url, filename = _resolve_direct_url_via_ytdlp(url, None)
print("Direct URL:", direct_url[:100] if direct_url else None)
print("Filename:", filename)
