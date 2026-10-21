FROM python:3.13-slim AS builder

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# create app directory to work in
WORKDIR /app

# install uv
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /bin/

# install python requirements
# copy just dependency file(s) and install before rest of code to avoid having to
# reinstall packages during build every time code changes
COPY uv.lock pyproject.toml ./
RUN uv sync --frozen --no-dev --group prod --no-install-project

# --- runtime stage ---
FROM python:3.13-slim

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Create an unprivileged user
RUN addgroup --system django && adduser --system --ingroup django --home /home/django django

WORKDIR /app

# Copy finished venv from builder stage
COPY --from=builder /opt/venv /opt/venv
COPY --chown=django:django . .

# Allow django user to write static and celery files
RUN mkdir -p /app/staticfiles /app/celerybeat \
    && chown -R django:django /app/staticfiles /app/celerybeat

# declare user to run commands
USER django

# declare ports which container exposess
EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
