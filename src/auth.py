import os
import time
import hmac
import hashlib
import base64


def generate_auth_token(email):
    expiry = int(time.time()) + (7 * 24 * 3600)  # 7 days
    payload = f"{email}:{expiry}"
    secret = os.environ.get("JWT_SECRET", "super_secret_key_clauster_blog").encode()
    signature = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    token_str = f"{payload}:{signature}"
    return base64.b64encode(token_str.encode()).decode()

def verify_auth_token(token):
    if not token:
        return False
    try:
        decoded = base64.b64decode(token.encode()).decode()
        parts = decoded.split(":")
        if len(parts) != 3:
            return False
        email, expiry, signature = parts
        if int(expiry) < time.time():
            return False
        payload = f"{email}:{expiry}"
        secret = os.environ.get("JWT_SECRET", "super_secret_key_clauster_blog").encode()
        expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected):
            admin_email = os.environ.get("ADMIN_EMAIL", "Instantreelsdownload@gmail.com")
            return email == admin_email
    except Exception:
        return False
    return False

