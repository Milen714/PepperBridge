FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server.py /app/server.py

EXPOSE 50005
CMD ["python3", "-u", "/app/server.py"]