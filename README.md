# OpenSchool sucks

[![Python application](https://github.com/Krupicova12Kase/OpenSchoolSucks/actions/workflows/python-app.yml/badge.svg)](https://github.com/Krupicova12Kase/OpenSchoolSucks/actions/workflows/python-app.yml)

## Deployment

Sessions are stored server-side (`flask_session/` via Flask-Session +
cachelib), not in the cookie itself, because the real is.psjg.cz login
cookies are too large to fit in a single signed client-side cookie. That
means the app needs a host with a persistent/writable filesystem across
requests - a normal server or container (the included `Dockerfile` targets
this: e.g. Google Cloud Run, Render, Fly.io, Railway).

**This does not work on stateless serverless platforms like Vercel** as-is:
each invocation can run in a different, ephemeral instance, so a
`flask_session/` file written by one request may not be there for the next,
which breaks login. Making it Vercel-compatible would require swapping the
session store for an external one shared across invocations (e.g. Redis /
Vercel KV) instead of the local filesystem - ask if you want that built.

### Deploying to Render

The included `render.yaml` blueprint targets the existing `Dockerfile`
as-is - Render runs it as one long-lived container (not per-request
functions), so the local `flask_session/` directory persists across
requests the way this app needs.

1. On [render.com](https://render.com), **New > Blueprint**, pick this repo/branch. It reads `render.yaml` and creates the service (region `frankfurt`, free plan by default - edit `render.yaml` to change either).
2. `SECRET_KEY` is generated automatically by the blueprint. Set `FRONTEND_ORIGIN` in the Render dashboard to your deployed frontend's exact origin (e.g. `https://openschool-umber.vercel.app` - no trailing slash, and list multiple as a comma-separated string if you have more than one).
3. Once deployed, copy the service's `https://<name>.onrender.com` URL and set it as `VITE_API_URL=https://<name>.onrender.com/api` on the frontend (e.g. in Vercel's project env vars), then redeploy the frontend.
4. Keep this service at a single instance - sessions live on that instance's local disk, so scaling to multiple replicas would (like Vercel) randomly lose sessions between requests, unless the session store is swapped for something shared like Redis.
5. Render's free plan spins the service down after inactivity; the first request after idle can take ~30-60s to cold-start.

Without the blueprint, the same works as **New > Web Service**, environment
"Docker" (auto-detected from `Dockerfile`), with the env vars above set by
hand.

Required environment variables:

- `SECRET_KEY` - required. Signs the session cookie.
- `VERIFY` - optional, defaults to `True`. Set to `False` to skip TLS
  verification against is.psjg.cz (not recommended).
- `DEBUG` - optional, defaults to `False`. Leave unset/`False` in production.
- `FRONTEND_ORIGIN` - optional, defaults to `http://localhost:5173,http://127.0.0.1:5173`.
  Comma-separated list of origins allowed to call the JSON API below with
  credentials (browsers reject `Access-Control-Allow-Origin: *` together with
  cookies, so the frontend's real origin(s) must be listed explicitly).
- `SESSION_COOKIE_SAMESITE` / `SESSION_COOKIE_SECURE` - optional. If the
  frontend (e.g. the [ispsjginjs](https://github.com/maxkunc/ispsjginjs) React
  app) is deployed on a *different domain* than this backend, the session
  cookie needs `SESSION_COOKIE_SAMESITE=None` and `SESSION_COOKIE_SECURE=True`
  (which requires HTTPS) for the browser to send it back on cross-origin API
  calls. Same-domain (or same-site, reverse-proxied) deployments can leave
  both unset.

## JSON API

Alongside the original server-rendered pages, the app exposes a small JSON
API (same login/scraping logic, same server-side session) for the
[ispsjginjs](https://github.com/maxkunc/ispsjginjs) React frontend:

- `GET  /api/session` - `{ authenticated }`
- `POST /api/login` - body `{ username, password }`
- `POST /api/logout`
- `GET  /api/home?page=N` - subjects, paginated grades, dashboard stats, semesters
- `POST /api/semester` - body `{ semester: "<label from /api/home>" }`
- `GET  /api/subject/<id>` - grades for one subject
- `GET  /api/portfolio` - portfolio points/place/categories
- `GET  /api/zkouseni` - placeholder (feature still WIP, see TODO.md)

All routes other than `/api/login` and `/api/session` return
`401 {"ok": false, "error": "not_authenticated"}` when there's no valid
session, mirroring the redirect-to-login behavior of the HTML routes.

## Fonts

Numeric LED-style readouts (grade badges, stat numbers, pagination) use
"LED Counter-7" by Sizenko Alexander / Style-Seven (http://www.styleseven.com/),
freeware for non-commercial/education use. See `static/fonts/led_counter-7-LICENSE.txt`.
