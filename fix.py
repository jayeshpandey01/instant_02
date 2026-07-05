import os
for f, bp in [('src/routes/api.py', '@api_bp.route'), ('src/routes/blog.py', '@blog_bp.route'), ('src/routes/views.py', '@views_bp.route')]:
    with open(f, 'r', encoding='utf-8') as file:
        data = file.read()
    with open(f, 'w', encoding='utf-8') as file:
        file.write(data.replace('@app.route', bp))
