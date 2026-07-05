import json
from flask import Blueprint, request, jsonify
from src.database import get_db_connection
from src.auth import verify_auth_token

blog_bp = Blueprint("blog", __name__)


@blog_bp.route("/api/blog")
def get_blogs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blogs ORDER BY id DESC")
        rows = cursor.fetchall()
        blogs = []
        for row in rows:
            blogs.append({
                "id": row["id"],
                "slug": row["slug"],
                "title": row["title"],
                "category": row["category"],
                "date": row["date"],
                "excerpt": row["excerpt"],
                "content": json.loads(row["content"]) if row["content"] else []
            })
        conn.close()
        return jsonify(blogs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@blog_bp.route("/api/blog/<slug>")
def get_blog_single(slug):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blogs WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return jsonify({
                "id": row["id"],
                "slug": row["slug"],
                "title": row["title"],
                "category": row["category"],
                "date": row["date"],
                "excerpt": row["excerpt"],
                "content": json.loads(row["content"]) if row["content"] else []
            })
        return jsonify({"error": "Blog post not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@blog_bp.route("/api/blog", methods=["POST"])
def create_blog():
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not verify_auth_token(token):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    title = data.get("title")
    slug = data.get("slug")
    category = data.get("category", "General")
    date = data.get("date") or time.strftime("%B %d, %Y")
    content = data.get("content")
    
    if not title or not slug or not content:
        return jsonify({"error": "Title, slug, and content are required"}), 400
        
    excerpt = data.get("excerpt") or (content[0][:150] + "..." if content else "")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO blogs (slug, title, category, date, excerpt, content) VALUES (?, ?, ?, ?, ?, ?)",
            (slug, title, category, date, excerpt, json.dumps(content))
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return jsonify({"id": new_id, "slug": slug, "title": title}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "A blog post with this slug already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@blog_bp.route("/api/blog/<int:blog_id>", methods=["PUT"])
def update_blog(blog_id):
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not verify_auth_token(token):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    title = data.get("title")
    slug = data.get("slug")
    category = data.get("category", "General")
    date = data.get("date") or time.strftime("%B %d, %Y")
    content = data.get("content")
    
    if not title or not slug or not content:
        return jsonify({"error": "Title, slug, and content are required"}), 400
        
    excerpt = data.get("excerpt") or (content[0][:150] + "..." if content else "")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE blogs SET slug = ?, title = ?, category = ?, date = ?, excerpt = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (slug, title, category, date, excerpt, json.dumps(content), blog_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Blog post updated successfully"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "A blog post with this slug already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@blog_bp.route("/api/blog/<int:blog_id>", methods=["DELETE"])
def delete_blog(blog_id):
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    if not verify_auth_token(token):
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blogs WHERE id = ?", (blog_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Blog post deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

