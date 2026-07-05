import os
import sqlite3
import json
from src.config import BASE_DIR


def get_db_connection():
    db_path = os.environ.get("DATABASE_PATH", "blog.db")
    if not os.path.isabs(db_path):
        if os.environ.get("VERCEL"):
            db_path = os.path.join("/tmp", db_path)
        else:
            db_path = os.path.join(os.path.dirname(__file__), db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            date TEXT,
            excerpt TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM blogs")
    if cursor.fetchone()[0] == 0:
        default_posts = [
            {
                "slug": "how-reclip-makes-downloads-easy",
                "title": "How Reclip Makes Downloads Effortless",
                "category": "Product",
                "date": "June 25, 2026",
                "excerpt": "A closer look at the small design choices that make every download feel calm, clear, and fast.",
                "content": json.dumps([
                    "Reclip was built to turn a complicated download flow into something that feels almost effortless. Instead of scattering options across several steps, the experience stays focused on one simple goal: getting your file ready without friction.",
                    "The secret is in the flow. You paste a link, choose a format, and the rest of the work happens smoothly in the background. That keeps the experience calm for first-time users and familiar for people who come back often.",
                    "Small details matter here too. Clear status feedback, polished buttons, and thoughtful copy all help create a sense of confidence while the download is being prepared."
                ])
            },
            {
                "slug": "why-creators-love-simple-media-tools",
                "title": "Why Creators Love Simple Media Tools",
                "category": "Creator Tips",
                "date": "June 20, 2026",
                "excerpt": "Creators often need quick access to media, and a simple workflow can save time and energy.",
                "content": json.dumps([
                    "When creators work across different platforms, speed matters. They often need to save a clip, grab an audio file, or revisit a piece of media quickly without losing momentum.",
                    "That is where simple tools shine. A polished experience helps creators keep moving instead of getting stuck in a maze of menus, redirects, or confusing steps.",
                    "Reclip focuses on that exact balance: minimal friction, clear choices, and a smooth finish so the work stays creative rather than technical."
                ])
            },
            {
                "slug": "best-practices-for-video-and-audio-downloads",
                "title": "Best Practices for Video and Audio Downloads",
                "category": "How-To",
                "date": "June 15, 2026",
                "excerpt": "A practical checklist for choosing the right format and quality before you hit download.",
                "content": json.dumps([
                    "Choosing between video and audio often depends on the purpose of the file. If you need a quick preview, a lower-quality option may be enough. If you want a more polished result, higher-quality settings are a better fit.",
                    "Audio-only downloads are ideal for podcasts, playlists, or content that will be reused in editing workflows. Video downloads are better when visual detail matters most.",
                    "The best approach is to match the format to the use case and keep the download experience simple enough that the choice feels easy instead of overwhelming."
                ])
            }
        ]
        for post in default_posts:
            cursor.execute(
                "INSERT INTO blogs (slug, title, category, date, excerpt, content) VALUES (?, ?, ?, ?, ?, ?)",
                (post["slug"], post["title"], post["category"], post["date"], post["excerpt"], post["content"])
            )
        conn.commit()
    conn.close()

