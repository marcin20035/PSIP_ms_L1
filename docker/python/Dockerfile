FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-venv gdal-bin python3-gdal ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
       h3==4.3.1 shapely==2.1.2 psycopg2-binary==2.9.10

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app