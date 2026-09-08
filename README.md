# OpenSchool sucks

[![Python application](https://github.com/Krupicova12Kase/OpenSchoolSucks/actions/workflows/python-app.yml/badge.svg)](https://github.com/Krupicova12Kase/OpenSchoolSucks/actions/workflows/python-app.yml)

## Deploying to Vercel

The app runs on Vercel as a Python serverless function (`vercel.json` routes
every request to `app.py`, which Vercel imports and serves as a WSGI app).

Set these environment variables in the Vercel project settings:

- `SECRET_KEY` - required. Signs the session cookie; use a long random value.
- `VERIFY` - optional, defaults to `True`. Set to `False` to skip TLS
  verification against is.psjg.cz (not recommended).
- `DEBUG` - optional, defaults to `False`. Leave unset/`False` in production.

Sessions are signed client-side cookies (Flask's default), not a server-side
store, so they work across the independent, ephemeral invocations a
serverless function runs in. The TLS certificate chain fetched from
is.psjg.cz on startup is cached under `/tmp` (the only writable path on
Vercel) instead of inside the repo.

## Fonts

Numeric LED-style readouts (grade badges, stat numbers, pagination) use
"LED Counter-7" by Sizenko Alexander / Style-Seven (http://www.styleseven.com/),
freeware for non-commercial/education use. See `static/fonts/led_counter-7-LICENSE.txt`.
