import os, json, threading, time
from flask import Flask, redirect, request, jsonify, session
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ.get("FLASK_SECRET", "change-this-before-deploying")
CORS(app, resources={r"/api/*": {"origins": "*"}})
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_FILE = "/tmp/youtube_token.json"
STATE = {"chat_id": None, "next_page": None, "messages": [], "last_poll": 0, "error": None}
LOCK = threading.Lock()


def client_config():
    raw = os.environ.get("GOOGLE_CLIENT_CONFIG")
    if not raw:
        raise RuntimeError("GOOGLE_CLIENT_CONFIG environment variable is missing")
    return json.loads(raw)


def redirect_uri():
    base = os.environ.get("RENDER_EXTERNAL_URL", request.host_url.rstrip("/"))
    return base.rstrip("/") + "/oauth2callback"


def save_creds(creds):
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())


def load_creds():
    if not os.path.exists(TOKEN_FILE):
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_creds(creds)
    return creds if creds.valid else None


def youtube_service():
    creds = load_creds()
    if not creds:
        return None
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


@app.get("/")
def home():
    return "Live Chat Message Writer backend is running. Open /health to check status."


@app.get("/health")
def health():
    return jsonify({"ok": True, "authorized": load_creds() is not None,
                    "chat_found": bool(STATE["chat_id"])})


@app.get("/auth")
def auth():
    flow = Flow.from_client_config(client_config(), scopes=SCOPES)
    flow.redirect_uri = redirect_uri()
    url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    session["oauth_state"] = state
    return redirect(url)


@app.get("/oauth2callback")
def oauth2callback():
    flow = Flow.from_client_config(
        client_config(), scopes=SCOPES, state=session.get("oauth_state")
    )
    flow.redirect_uri = redirect_uri()
    authorization_response = request.url.replace("http://", "https://", 1)
    flow.fetch_token(authorization_response=authorization_response)
    save_creds(flow.credentials)
    return "YouTube connected successfully. You can return to PRISM."


@app.get("/api/names")
def names():
    svc = youtube_service()
    if svc is None:
        return jsonify({"error": "YouTube not connected. Open /auth first.", "chat_found": False,
                        "messages": [], "names": []}), 401

    now = time.time()
    with LOCK:
        if now - STATE["last_poll"] >= 5:
            STATE["last_poll"] = now
            try:
                if not STATE["chat_id"]:
                    broadcasts = svc.liveBroadcasts().list(
                        part="id,snippet,contentDetails,status",
                         mine=True, maxResults=5
                    ).execute()
                    for item in broadcasts.get("items", []):
                        chat_id = item.get("snippet", {}).get("liveChatId")
                        if chat_id:
                            STATE["chat_id"] = chat_id
                            break

                if STATE["chat_id"]:
                    kwargs = {"liveChatId": STATE["chat_id"], "part": "snippet,authorDetails",
                              "maxResults": 200}
                    if STATE["next_page"]:
                        kwargs["pageToken"] = STATE["next_page"]
                    result = svc.liveChatMessages().list(**kwargs).execute()

                    for item in result.get("items", []):
                        snippet = item.get("snippet", {})
                        author = item.get("authorDetails", {}).get("displayName", "").strip()
                        message = ""
                        # Regular viewer chat messages
                        if snippet.get("type") == "textMessageEvent":
                            message = snippet.get("textMessageDetails", {}).get("messageText", "").strip()
                        # Also show a viewer's written comment on a Super Chat
                        elif snippet.get("type") == "superChatEvent":
                            message = snippet.get("superChatDetails", {}).get("userComment", "").strip()

                        if message:
                            STATE["messages"].append({
                                "id": item.get("id"),
                                "author": author,
                                "message": message
                            })

                    STATE["messages"] = STATE["messages"][-30:]
                    STATE["next_page"] = result.get("nextPageToken")
                    STATE["error"] = None
            except Exception as exc:
                STATE["error"] = str(exc)

        messages = list(STATE["messages"])

    # Keep the old key for compatibility; the frontend now uses `messages`.
    return jsonify({"messages": messages, "names": messages,
                    "chat_found": bool(STATE["chat_id"]), "error": STATE["error"]})


if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
    
