"""
OAuth2 flow to generate a refresh token for Google Ads API.

This script:
1. Reads your OAuth2 client credentials JSON
2. Opens a browser for Google sign-in
3. Captures the authorization code via a local redirect
4. Exchanges it for a refresh token
5. Updates google-ads.yaml with the refresh token
"""

import json
import sys
import yaml
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "client-secrects-google-mcp.json"
GOOGLE_ADS_YAML_PATH = PROJECT_ROOT / "google-ads.yaml"
SCOPES = ["https://www.googleapis.com/auth/adwords"]
REDIRECT_URI = "http://localhost:8089"

auth_code_holder = {"code": None}


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            auth_code_holder["code"] = query["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization successful!</h2>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            error = query.get("error", ["unknown"])[0]
            self.wfile.write(f"<html><body><h2>Error: {error}</h2></body></html>".encode())

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


def load_client_credentials():
    with open(CREDENTIALS_PATH) as f:
        data = json.load(f)
    creds = data.get("installed") or data.get("web")
    if not creds:
        print("ERROR: Credentials JSON must have an 'installed' or 'web' key.")
        sys.exit(1)
    return creds["client_id"], creds["client_secret"]


def build_auth_url(client_id):
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"


def exchange_code_for_tokens(client_id, client_secret, code):
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    resp.raise_for_status()
    return resp.json()


def update_google_ads_yaml(refresh_token):
    with open(GOOGLE_ADS_YAML_PATH) as f:
        config = yaml.safe_load(f)
    config["refresh_token"] = refresh_token
    with open(GOOGLE_ADS_YAML_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    print(f"\nRefresh token saved to {GOOGLE_ADS_YAML_PATH}")


def main():
    print("=== Google Ads OAuth2 Refresh Token Generator ===\n")

    client_id, client_secret = load_client_credentials()
    print(f"Client ID: {client_id[:20]}...")

    # Start local server to capture the redirect
    server = HTTPServer(("localhost", 8089), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    # Open browser for authorization
    auth_url = build_auth_url(client_id)
    print(f"\nOpening browser for authorization...")
    print(f"If the browser doesn't open, visit this URL manually:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Wait for the callback
    print("Waiting for authorization callback...")
    server_thread.join(timeout=120)
    server.server_close()

    if not auth_code_holder["code"]:
        print("ERROR: Did not receive authorization code within 2 minutes.")
        sys.exit(1)

    print("Authorization code received. Exchanging for tokens...")
    tokens = exchange_code_for_tokens(client_id, client_secret, auth_code_holder["code"])

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("ERROR: No refresh token in response. Make sure prompt=consent is set.")
        print(f"Response: {tokens}")
        sys.exit(1)

    print(f"\nRefresh Token: {refresh_token[:20]}...")
    update_google_ads_yaml(refresh_token)
    print("\nDone! Your google-ads.yaml is now configured with the refresh token.")


if __name__ == "__main__":
    main()
