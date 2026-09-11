import os
import requests, re

# Read credentials from environment to avoid storing secrets in repo
EMAIL = os.environ.get('TEST_LOGIN_EMAIL', 'nonexistent@example.com')
PASSWORD = os.environ.get('TEST_LOGIN_PASSWORD', 'wrongpass')

s = requests.Session()
url = 'http://127.0.0.1:5000/login'
try:
    r = s.get(url, timeout=10)
    print('GET', r.status_code)
    print('cookies after GET:', s.cookies.get_dict())
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', r.text)
    token = m.group(1) if m else None
    print('csrf_token found:', bool(token))
    data = {'email': EMAIL, 'password': PASSWORD}
    if token:
        data['csrf_token'] = token
    # Debug info (do not print password)
    safe_data_keys = list(data.keys())
    print('posting keys:', safe_data_keys)
    print('csrf token present in payload:', 'csrf_token' in data)
    r2 = s.post(url, data=data, allow_redirects=False, timeout=10)
    # Show request headers for debugging
    try:
        print('request headers:', dict(r2.request.headers))
    except Exception:
        pass
    print('POST', r2.status_code)
    print('Location:', r2.headers.get('Location'))
    print('Body snippet:\n', r2.text[:800])
except Exception as e:
    print('Error during request:', e)
