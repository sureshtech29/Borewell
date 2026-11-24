# Multi-stage Dockerfile: builds React frontend and serves with FastAPI backend in one container
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
        fonts-noto-core fonts-lohit-telu fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* && fc-cache -f

WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/config ./config
COPY backend/demo ./demo
COPY backend/scripts ./scripts

# Copy frontend build output to static folder
COPY --from=frontend-builder /app/frontend/dist ./static

RUN useradd --system --uid 10001 bwf && mkdir -p /srv/models && chown -R bwf /srv
USER bwf

# 7860 is Hugging Face Spaces default port, also supports cloud $PORT
EXPOSE 7860 8000 8080

ENV APP_DATA_MODE=demo
ENV APP_DATA_BACKEND=memory
ENV PORT=7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --no-access-log --proxy-headers --forwarded-allow-ips=*"]
