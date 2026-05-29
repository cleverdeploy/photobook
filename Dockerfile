FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

# SQLite DB + uploaded photos live under /data. Persistence comes from an
# explicit Dokploy volume mounted at /data — NOT a Docker VOLUME directive
# (which would just create a throwaway anonymous volume per deploy).
RUN mkdir -p /data

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
