# OpenSchool sucks

[![Python application](https://github.com/Krupicova12Kase/OpenSchoolSucks/actions/workflows/python-app.yml/badge.svg)](https://github.com/Krupicova12Kase/OpenSchoolSucks/actions/workflows/python-app.yml)

Flask backend for the is.psjg.cz grades dashboard: logs into is.psjg.cz,
scrapes grades/subjects/portfolio, and exposes them as a small JSON API. The
UI itself lives in a separate repo, [ispsjginjs](https://github.com/maxkunc/ispsjginjs)
(React + Tailwind) - this backend's `Dockerfile` builds that repo and serves
the result itself, so the deployed app is a single service on a single
origin. There is no separate frontend host, and no `VITE_API_URL` /
`FRONTEND_ORIGIN` / CORS to configure - `/api/*` calls from the UI are
same-origin by construction.

## Deployment

Sessions are stored server-side (in a tmp dir via Flask-Session + cachelib),
not in the cookie itself, because the real is.psjg.cz login cookies are too
large to fit in a single signed client-side cookie. That means the app needs
a host that runs it as a long-lived container/process (not a *stateless*
serverless platform like Vercel, where each invocation can land on a
different ephemeral instance and lose that session data between requests).

### Deploying to Render

The included `render.yaml` blueprint targets the existing `Dockerfile`
as-is - Render runs it as one long-lived container, which is what this app
needs, and the multi-stage `Dockerfile` builds the `ispsjginjs` frontend
into it during the image build (see `Dockerfile`'s `frontend` stage).

1. On [render.com](https://render.com), **New > Blueprint**, pick this repo/branch. It reads `render.yaml` and creates the service (region `frankfurt`, free plan by default - edit `render.yaml` to change either).
2. `SECRET_KEY` is generated automatically by the blueprint. Nothing else is required.
3. That's it - open the service's `https://<name>.onrender.com` URL and the React UI is served directly from there.
4. Keep this service at a single instance - sessions live on that instance's local disk, so scaling to multiple replicas would randomly lose sessions between requests, unless the session store is swapped for something shared like Redis.
5. Render's free plan spins the service down after inactivity; the first request after idle can take ~30-60s to cold-start.

Without the blueprint, the same works as **New > Web Service**, environment
"Docker" (auto-detected from `Dockerfile`).

Building a different branch/fork of the frontend? The `Dockerfile`'s
`frontend` stage takes `FRONTEND_REPO`, `FRONTEND_REF`, and
`FRONTEND_COMMIT_API` build args (defaults: this account's `ispsjginjs`,
branch `main`) - pass them via `docker build --build-arg ...` if building
elsewhere, or your host's Docker build-args setting if it has one.
`FRONTEND_COMMIT_API` must point at the same repo/ref as the other two if
you override them - it's a GitHub API URL the build fetches on every
build specifically to invalidate Docker's cache for the `git clone` step
below it when there's a new commit (a plain `git clone` has identical
instruction text every build, so without this a stale, long-cached clone
of the frontend could silently outlive many new pushes to it).

Required environment variables:

- `SECRET_KEY` - required. Signs the session cookie.
- `VERIFY` - optional, defaults to `True`. Set to `False` to skip TLS
  verification against is.psjg.cz (not recommended).
- `DEBUG` - optional, defaults to `False`. Leave unset/`False` in production.
- `SESSION_COOKIE_SECURE` - optional, defaults to `False`. Set to `True` in
  production (anywhere served over HTTPS, which Render is) so the session
  cookie is never sent over plain HTTP.
- `SESSION_COOKIE_SAMESITE` - optional, defaults to `Lax`. No reason to
  change this now that frontend and backend are always same-origin.

### Running the frontend separately instead

The API (see below) is still there if you'd rather deploy `ispsjginjs`
on its own (e.g. to iterate on the UI without rebuilding this image each
time) - see its README for `VITE_API_URL` and this backend's now-optional
`FRONTEND_ORIGIN`-style CORS needs. That path is no longer the recommended
one, just still supported.

## JSON API

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
session.

Every other path (`/`, `/login`, `/subject/1`, ...) serves the built React
app's `index.html`, letting the client-side router handle it - see
`serve_frontend()` in `app.py`.

## Local development

Run the two apps separately rather than through Docker:

```bash
pip install -r requirements.txt
SECRET_KEY=devsecret python app.py       # backend on :5000
```

```bash
cd ../ispsjginjs
npm install
npm run dev                              # frontend on :5173, proxies /api to :5000
```

Hitting this Flask server's own `/` directly (without the Vite dev server)
just returns a short explanatory message, since `frontend_dist/` (the built
React app) only exists inside the Docker image.

## Fonts

Numeric LED-style readouts (grade badges, stat numbers, pagination) use
"LED Counter-7" by Sizenko Alexander / Style-Seven (http://www.styleseven.com/),
freeware for non-commercial/education use - see `ispsjginjs`'s
`public/fonts/led_counter-7-LICENSE.txt` (this repo no longer serves any
static assets directly).
