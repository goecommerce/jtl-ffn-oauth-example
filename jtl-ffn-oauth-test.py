import json, base64, secrets, webbrowser, time, requests
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlencode

CLIENT_ID = "deine-client-id-hier"
CLIENT_SECRET = "dein-client-secret-hier"
REDIRECT_URI = "https://deine-webhook-url.de/callback"

API_BASE = "https://ffn-sbx.api.jtl-software.com/api"
OAUTH_AUTHORIZE = "https://oauth2.api.jtl-software.com/authorize"
OAUTH_TOKEN = "https://oauth2.api.jtl-software.com/token"
SCOPES = "ffn.merchant.read ffn.merchant.write ffn.fulfiller.read ffn.fulfiller.write address email phone profile"
TOKEN_FILE = Path("ffn_token.json")

def save_tokens(access_token, refresh_token, expires_in):
    TOKEN_FILE.write_text(json.dumps({"access_token": access_token, "refresh_token": refresh_token, "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat()}, indent=2))

def load_tokens():
    if not TOKEN_FILE.exists():
        return None
    data = json.loads(TOKEN_FILE.read_text())
    data["expires_at_dt"] = datetime.fromisoformat(data["expires_at"])
    return data

def get_auth_code():
    auth_url = f"{OAUTH_AUTHORIZE}?{urlencode({'response_type': 'code', 'client_id': CLIENT_ID, 'redirect_uri': REDIRECT_URI, 'scope': SCOPES, 'state': secrets.token_urlsafe(16)})}"
    print("Browser öffnet sich...")
    webbrowser.open(auth_url)
    time.sleep(5)
    for i in range(12):
        try:
            resp = requests.get(REDIRECT_URI, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                code = data.get('authorization_code')
                if code and data.get('success'):
                    print("Code empfangen")
                    return code
        except:
            pass
        time.sleep(5)
    code = input("Code manuell eingeben: ").strip()
    if not code:
        raise Exception("Kein Code")
    return code

def get_token_from_code(code):
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(OAUTH_TOKEN, headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/x-www-form-urlencoded'}, data={'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI}, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Token exchange failed: {resp.status_code}")
    data = resp.json()
    save_tokens(data['access_token'], data['refresh_token'], data['expires_in'])
    return data

def refresh_token(refresh_token):
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp = requests.post(OAUTH_TOKEN, headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/x-www-form-urlencoded'}, data={'grant_type': 'refresh_token', 'refresh_token': refresh_token}, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Refresh failed: {resp.status_code}")
    data = resp.json()
    save_tokens(data['access_token'], data['refresh_token'], data['expires_in'])
    return data

def get_valid_token():
    tokens = load_tokens()
    if not tokens:
        print("Starte OAuth...")
        code = get_auth_code()
        tokens = get_token_from_code(code)
        print(f"Autorisiert - läuft ab: {(datetime.now() + timedelta(seconds=tokens['expires_in'])).strftime('%H:%M:%S')}")
        return tokens['access_token']
    expires_at = tokens['expires_at_dt']
    seconds_left = int((expires_at - datetime.now()).total_seconds())
    print(f"Token läuft ab: {expires_at.strftime('%H:%M:%S')} (in {seconds_left}s)")
    if datetime.now() >= expires_at - timedelta(seconds=60):
        print("Refreshe Token...")
        try:
            tokens = refresh_token(tokens['refresh_token'])
            print(f"Refreshed - läuft ab: {(datetime.now() + timedelta(seconds=tokens['expires_in'])).strftime('%H:%M:%S')}")
            return tokens['access_token']
        except:
            print("Refresh failed - starte neu...")
            TOKEN_FILE.unlink(missing_ok=True)
            code = get_auth_code()
            tokens = get_token_from_code(code)
            print(f"Neu autorisiert - läuft ab: {(datetime.now() + timedelta(seconds=tokens['expires_in'])).strftime('%H:%M:%S')}")
            return tokens['access_token']
    print("Token OK")
    return tokens['access_token']

if __name__ == "__main__":
    print("\nJTL-FFN OAuth Test Tool")

    token = get_valid_token()
    resp = requests.get(f"{API_BASE}/v1/users/current", headers={'Authorization': f'Bearer {token}'}, timeout=30)
    resp.raise_for_status()
    user = resp.json()
    print(f"API OK - User: {user['userId']}\n")