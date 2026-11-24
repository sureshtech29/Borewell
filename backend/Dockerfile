# Borewell Water Finder - API image.
# WeasyPrint needs Pango; Telugu text needs Telugu fonts (otherwise PDFs show empty boxes).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
        fonts-noto-core fonts-lohit-telu fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* && fc-cache -f

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config
COPY demo ./demo
COPY scripts ./scripts

RUN useradd --system --uid 10001 bwf && mkdir -p /srv/models && chown bwf /srv/models
USER bwf
EXPOSE 8000

# --no-access-log: the access log would record the query string, i.e. the coordinates users look up.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips=*"]
