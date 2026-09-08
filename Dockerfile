# --- Frontend build stage: builds the React app from the separate ---
# --- ispsjginjs repo, so this stays a single deployable service.    ---
FROM node:20-slim AS frontend

WORKDIR /frontend

ARG FRONTEND_REPO=https://github.com/maxkunc/ispsjginjs.git
ARG FRONTEND_REF=main
# Must name the same repo/ref as FRONTEND_REPO/FRONTEND_REF above if you
# override those - see the ADD instruction below for why this exists.
ARG FRONTEND_COMMIT_API=https://api.github.com/repos/maxkunc/ispsjginjs/commits/main

RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Unlike RUN, ADD re-checks its URL's content on every build and invalidates
# the cache from here down when it changed. `git clone` below has identical
# instruction text on every build, so without this Docker would silently
# keep reusing whatever commit got cloned the very first time this stage
# ever ran - new pushes to ispsjginjs would never reach a deployed image.
ADD ${FRONTEND_COMMIT_API} /tmp/frontend-head.json

RUN git clone --depth 1 --branch ${FRONTEND_REF} ${FRONTEND_REPO} .
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
