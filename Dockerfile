ARG PYTHON_BASE=python:3.13-slim

FROM node:20-bookworm-slim AS node_runtime
FROM ${PYTHON_BASE}

ARG INSTALL_REQUIREMENTS=1
ARG PYTHON_COMMAND=/opt/venv/bin/python

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TENDERBRIEF_PYTHON=${PYTHON_COMMAND} \
    HOST=127.0.0.1 \
    PORT=4174 \
    API_PORT=4174 \
    UI_HOST=0.0.0.0 \
    UI_PORT=4173

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN if [ "$INSTALL_REQUIREMENTS" = "1" ]; then \
        python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .
RUN if ! id app >/dev/null 2>&1; then useradd --create-home --uid 10001 app; fi \
    && mkdir -p /app/work \
    && chown -R app:app /app/work

USER app
EXPOSE 4173
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4173/api/health', timeout=3).read()"]
ENTRYPOINT ["node"]
CMD ["server.mjs"]
