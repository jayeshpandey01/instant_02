import ast
import sys

def extract(functions, out_file, imports, bp_replace=None):
    with open('app.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    tree = ast.parse(source)
    extracted_source = imports + "\n\n"
    
    for name in functions:
        if name == "jobs_dict":
            extracted_source += "jobs = {}\n\n"
            continue
            
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == name:
                    segment = ast.get_source_segment(source, node)
                    if bp_replace:
                        segment = segment.replace("@app.route", bp_replace)
                    extracted_source += segment + "\n\n"
                    
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(extracted_source)

# 1. config.py
extract(["load_env"], "src/config.py", '''import os

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
''')

# 2. database.py
extract(["get_db_connection", "init_db"], "src/database.py", '''import os
import sqlite3
import json
from src.config import BASE_DIR
''')

# 3. auth.py
extract(["generate_auth_token", "verify_auth_token"], "src/auth.py", '''import os
import time
import hmac
import hashlib
import base64
''')

# 4. downloader.py
extract(["ensure_ffmpeg", "get_cookie_opts", "find_matching_cookie_file", "run_ytdlp_with_fallback", "needs_transcoding", "convert_to_ios_compatible_mp4"], "src/downloader.py", '''import os
import shutil
import tempfile
import urllib.request
import zipfile
import subprocess
import yt_dlp
import glob
from urllib.parse import urlparse
from src.config import BASE_DIR, DOWNLOAD_DIR
''')

# 5. tasks.py
extract(["jobs_dict", "cleanup_loop", "run_download"], "src/tasks.py", '''import os
import time
import glob
import shutil
import re
from src.config import DOWNLOAD_DIR
from src.downloader import run_ytdlp_with_fallback, convert_to_ios_compatible_mp4
''')

# 6. routes/views.py
extract(["index"], "src/routes/views.py", '''import os
from flask import Blueprint, render_template, send_file
from src.config import BASE_DIR

views_bp = Blueprint("views", __name__)
''', "@views_bp.route")

# 7. routes/blog.py
extract(["get_blogs", "get_blog_single", "create_blog", "update_blog", "delete_blog"], "src/routes/blog.py", '''import json
from flask import Blueprint, request, jsonify
from src.database import get_db_connection
from src.auth import verify_auth_token

blog_bp = Blueprint("blog", __name__)
''', "@blog_bp.route")

# 8. routes/api.py
extract(["admin_login", "list_cookie_files", "get_info", "get_playlist_info", "start_download", "check_status", "download_file", "cleanup_jobs"], "src/routes/api.py", '''import os
from flask import Blueprint, request, jsonify, send_file, after_this_request
from src.config import DOWNLOAD_DIR, BASE_DIR
from src.auth import generate_auth_token
from src.downloader import run_ytdlp_with_fallback
from src.tasks import jobs, run_download
import threading
import uuid
import shutil
import glob
import re

api_bp = Blueprint("api", __name__)
''', "@api_bp.route")

print("Extraction complete.")
