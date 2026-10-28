"""One-time YouTube login. Run on your own computer:

    python scripts/get_youtube_token.py CLIENT_ID CLIENT_SECRET

It opens Google's sign-in page in your browser. Sign in with the Dadabase Daily channel's
Google account and click Allow. The script then prints a refresh token: paste it into the
GitHub secret YT_REFRESH_TOKEN. Don't share it anywhere else.

Uses only the Python standard library.
"""
import base64
import hashlib
import http.server
import json
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser

PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}"
SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    client_id, client_secret = sys.argv[1], sys.argv[2]
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                result["code"] = q["code"][0]
                msg = "Done. You can close this tab and go back to the terminal."
            else:
                msg = "Something went wrong. Check the terminal."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(msg.encode())

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    print("Opening Google sign-in in your browser...\nIf it doesn't open, visit:\n" + url + "\n")
    webbrowser.open(url)
    while "code" not in result:
        server.handle_request()

    data = urllib.parse.urlencode({
        "code": result["code"], "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code", "code_verifier": verifier,
    }).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data)) as r:
        tokens = json.loads(r.read())
    if "refresh_token" not in tokens:
        print("Google didn't return a refresh token. Remove the app's access at myaccount.google.com/permissions and run again.")
        sys.exit(1)
    print("\nYour YouTube refresh token (paste into the GitHub secret YT_REFRESH_TOKEN):\n")
    print(tokens["refresh_token"])


if __name__ == "__main__":
    main()
