import requests

cookies = {}
with open('test_cookies.txt', 'r') as f:
    for line in f:
        if not line.strip() or line.startswith('#'): continue
        parts = line.strip().split('\t')
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]

headers = {
    'User-Agent': 'Instagram 219.0.0.12.117 Android',
    'x-ig-app-id': '936619743392459',
}
r1 = requests.get('https://i.instagram.com/api/v1/music/track/1136966408192134/', headers=headers, cookies=cookies)
print("1:", r1.status_code, r1.text[:200])

r2 = requests.get('https://www.instagram.com/api/v1/clips/music/1136966408192134/', headers={'x-ig-app-id': '936619743392459'}, cookies=cookies)
print("2:", r2.status_code, r2.text[:200])
