# --- Frontend build stage: builds the React app from the separate ---
# --- ispsjginjs repo, so this stays a single deployable service.    ---
FROM node:20-slim AS frontend

WORKDIR /frontend

ARG FRONTEND_REPO=https://github.com/maxkunc/ispsjginjs.git
ARG FRONTEND_REF=main

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

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
