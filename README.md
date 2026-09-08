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

Required environment variables:

- `SECRET_KEY` - required. Signs the session cookie.
- `VERIFY` - optional, defaults to `True`. Set to `False` to skip TLS
  verification against is.psjg.cz (not recommended).
- `DEBUG` - optional, defaults to `False`. Leave unset/`False` in production.

## Fonts

Numeric LED-style readouts (grade badges, stat numbers, pagination) use
"LED Counter-7" by Sizenko Alexander / Style-Seven (http://www.styleseven.com/),
freeware for non-commercial/education use. See `static/fonts/led_counter-7-LICENSE.txt`.
