# MOON TikTok Checker — backend

A tiny Flask API with one endpoint: `GET /api/tiktok?url=<tiktok video link>`.
It fetches the TikTok video page itself and reads TikTok's own embedded
data (no third-party scraping API, no headless browser). See the comment
at the top of `app.py` for details on why this approach was chosen.

## Run it locally (to test)

```bash
pip install -r requirements.txt
python app.py
```

Then test it:

```bash
curl "http://localhost:5000/api/tiktok?url=https://www.tiktok.com/@moonaee26/video/7661038718714645780"
```

You should get back JSON like:

```json
{"code": 0, "data": {"id": "...", "stats": {"playCount": 123, ...}, "video": {...}}}
```

## Deploy it for real (so your live site can call it)

Any of these work — pick whichever you're comfortable with. All have a
free tier that's enough for this.

### Option A — Render.com (easiest, no command line needed)
1. Push this `tiktok-checker-backend` folder to a GitHub repo (can be a
   new small repo just for this).
2. On [render.com](https://render.com) → **New +** → **Web Service** →
   connect that repo.
3. Build command: `pip install -r requirements.txt`
   Start command: `gunicorn app:app`
4. Deploy. Render gives you a URL like `https://your-app.onrender.com`.

### Option B — Railway.app
1. Push the folder to GitHub.
2. [railway.app](https://railway.app) → **New Project** → **Deploy from
   GitHub repo**.
3. Railway auto-detects Python; set the start command to `gunicorn app:app`
   if it doesn't pick it up automatically.
4. It gives you a public URL similar to Render's.

### Option C — Your own VPS
```bash
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8000 app:app
```
Put it behind nginx/Caddy with HTTPS (a plain `https://` domain or
subdomain, e.g. `api.yourdomain.com`), since the site itself is served
over HTTPS and browsers block a plain-HTTP API call from an HTTPS page.

## Wire it into the site

Once deployed, open the site's `index.html`, find this line near the top
of the "TIKTOK LINK CHECKER" script section:

```js
const TT_BACKEND_URL = ''; // e.g. 'https://your-app.onrender.com/api/tiktok'
```

and put your deployed URL (ending in `/api/tiktok`) in there. The
checker will call it first, and only fall back to the tikwm.com +
CORS-proxy chain if this isn't set or isn't reachable — so the site
keeps working either way, it just gets more reliable once this is live.

## A couple of honest caveats

- TikTok occasionally changes the internal page structure this reads.
  If checks suddenly start failing, that's the most likely reason — the
  fix is usually small (update the JSON-parsing part of `app.py`), but
  it's not something that fixes itself.
- Very heavy traffic from one server IP could get temporarily rate
  limited by TikTok, same as any script hitting their pages repeatedly.
  For normal use (a visitor pasting a link now and then) this shouldn't
  be an issue.
