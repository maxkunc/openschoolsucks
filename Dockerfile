# --- Frontend build stage: builds the React app from the separate ---
# --- ispsjginjs repo, so this stays a single deployable service.    ---
FROM node:20-slim AS frontend

WORKDIR /frontend

ARG FRONTEND_REPO=https://github.com/maxkunc/ispsjginjs.git
ARG FRONTEND_REF=main
# Pinned to a specific commit of ispsjginjs. This is what actually makes
# rebuilds happen: a plain `git clone` has identical instruction text on
# every build, so Docker has no way to know the remote changed and just
# reuses its cached layer forever (an ADD-from-URL trick to get Docker to
# re-check was tried here and didn't reliably force a fresh check on
# Render's build system either). Bumping this value's TEXT, which lives
# in this Dockerfile - i.e. in this repo, whose own content changes are
# already known to correctly bust cache below (see the COPY at the bottom
# of this file) - is what invalidates the git-clone layer when it needs to.
# Update this to ispsjginjs's new HEAD commit every time it changes:
#   git -C ../ispsjginjs rev-parse HEAD
ARG FRONTEND_COMMIT=7e0de64a6e34764655210c3751431bfdb77a8201

RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN git clone --branch ${FRONTEND_REF} ${FRONTEND_REPO} . && git checkout ${FRONTEND_COMMIT}
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

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
