LIVE NAME WRITER - BACKEND

1. Create a GitHub repository and upload app.py, requirements.txt, and render.yaml.
2. In Render, create a Web Service from that GitHub repository.
3. Build command: pip install -r requirements.txt
   Start command: python app.py
4. After deploy, copy the Render URL. OAuth redirect URI must be:
   https://YOUR-RENDER-SERVICE.onrender.com/oauth2callback
5. In Google Cloud > OAuth Client (Web application):
   - Authorized redirect URI: the exact URI above.
   - Authorized JavaScript origins are not needed for this backend.
6. In Render > Environment, add:
   GOOGLE_CLIENT_CONFIG = the full downloaded OAuth client JSON content
   FLASK_SECRET = a long random secret
7. Open https://YOUR-RENDER-SERVICE.onrender.com/auth and authorize the Google account
   that owns/manages the YouTube channel.
8. Start a public or unlisted YouTube live stream with live chat enabled.
9. Test /api/names. The backend polls the active live chat for display names.

SECURITY:
- Never paste OAuth client JSON, client secret, tokens, or passwords into chat.
- Keep the OAuth app in Testing while testing. Add the channel-owning Google account
  as a test user.
- This sample stores the OAuth token in /tmp, which can be lost when a free service
  restarts/redeploys. Re-authorize at /auth if that happens.
- This backend only reads live chat display names. It does not send messages or gifts.
