FROM node:20-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TENDERBRIEF_PYTHON=/opt/venv/bin/python \
    HOST=127.0.0.1 \
    PORT=4174 \
    API_PORT=4174 \
    UI_HOST=0.0.0.0 \
    UI_PORT=4173

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/work && chown -R node:node /app/work

USER node
EXPOSE 4173
CMD ["node", "server.mjs"]
