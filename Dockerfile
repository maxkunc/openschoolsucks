# --- Frontend build stage: builds the React app from the separate ---
# --- ispsjginjs repo, so this stays a single deployable service.    ---
FROM node:20-slim AS frontend

WORKDIR /frontend

ARG FRONTEND_OWNER=maxkunc
ARG FRONTEND_REPO_NAME=ispsjginjs
# Pinned to a specific commit of ispsjginjs. This is what actually makes
# rebuilds happen: a fetch with identical instruction text on every build
# gives Docker no signal that the remote changed, so it just reuses its
# cached layer forever. Bumping this value's TEXT, which lives in this
# Dockerfile - i.e. in this repo, whose own content changes are already
# known to correctly bust cache below (see the COPY at the bottom of this
# file) - is what invalidates this layer when it needs to.
# Update this to ispsjginjs's new HEAD commit every time it changes:
#   git -C ../ispsjginjs rev-parse HEAD
ARG FRONTEND_COMMIT=fb94b0ee02dd52fbcdb410045fb0b3d0e570a77b

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# A plain tarball download instead of `git clone`: codeload.github.com
# serves it over ordinary HTTPS, so there's no git-smart-http protocol
# handshake to fail - `git clone` here started hitting
# "fatal: could not read Username for 'https://github.com'" on Render's
# build network even against this public repo (most likely GitHub
# rate-limiting/challenging anonymous git operations from cloud build
# IP ranges, unrelated to repo visibility). This sidesteps that failure
# mode entirely.
RUN curl -fsSL "https://github.com/${FRONTEND_OWNER}/${FRONTEND_REPO_NAME}/archive/${FRONTEND_COMMIT}.tar.gz" \
    | tar -xz --strip-components=1
RUN npm ci
RUN npm run build

# --- Backend image ---
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /frontend/dist ./frontend_dist

ENV PYTHONPATH=/app
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# --threads capped at 4 (was 8): each concurrent request here can fan out
# into ~4 upstream calls to is.psjg.cz (session/home/portfolio/exams), so a
# high thread count turns a burst of students loading the dashboard at once
# into a much larger burst of simultaneous connections to that small backend
# than they'd generate browsing the real site by hand.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 0 app:app
