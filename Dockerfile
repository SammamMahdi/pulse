# syntax=docker/dockerfile:1
# Base image pinned by digest (reproducible builds); Dependabot proposes digest updates weekly.

# ---- build stage: install pinned dependencies into an isolated venv ----
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install --no-deps -r /tmp/requirements.txt \
 && /opt/venv/bin/pip uninstall --yes --quiet pip
COPY app/ /srv/app/
RUN /opt/venv/bin/python -m compileall -q /srv/app /opt/venv

# ---- runtime stage: no build tooling, no pip in the venv, non-root user ----
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS runtime
ARG APP_VERSION=0.0.0-dev
LABEL org.opencontainers.image.title="pulse-api" \
      org.opencontainers.image.description="Small FastAPI workload for the DevOps portfolio" \
      org.opencontainers.image.source="https://github.com/SammamMahdi/pulse" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${APP_VERSION}"
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION}
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /srv
# Code stays root-owned, so the app user cannot modify it.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /srv/app /srv/app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]
# Exec form: uvicorn is PID 1 and receives SIGTERM directly for graceful shutdown.
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--timeout-graceful-shutdown", "20"]
