import requests

BASE_URL = "http://127.0.0.1:8899"

def test_homepage():
    try:
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.content or b"<html" in response.content
        print("PASS: Homepage loaded")
    except Exception as e:
        print(f"FAIL: Homepage test failed: {e}")
        assert False

def test_api_cookie_files():
    try:
        response = requests.get(f"{BASE_URL}/api/cookie-files")
        assert response.status_code == 200
        assert isinstance(response.json().get("files"), list)
        print("PASS: Cookie files API")
    except Exception as e:
        print(f"FAIL: Cookie files API failed: {e}")
        assert False

def test_api_info_invalid_url():
    try:
        response = requests.post(f"{BASE_URL}/api/info", json={"url": "not_a_url"})
        assert response.status_code == 400
        assert "error" in response.json()
        print("PASS: Invalid URL validation")
    except Exception as e:
        print(f"FAIL: Invalid URL validation failed: {e}")
        assert False

def test_api_file_not_found():
    try:
        response = requests.get(f"{BASE_URL}/api/file/non_existent_job_id")
        assert response.status_code == 404
        assert "error" in response.json()
        print("PASS: File download 404 handler")
    except Exception as e:
        print(f"FAIL: File download 404 handler failed: {e}")
        assert False


if __name__ == "__main__":
    print("Running E2E tests against live server...")
    test_homepage()
    test_api_cookie_files()
    test_api_info_invalid_url()
    test_api_file_not_found()
    print("All tests passed!")
