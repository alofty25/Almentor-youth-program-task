# =============================================================================
#  Dockerfile — Almentor Task Management API
#  Build:  docker build -t almentor-api .
#  Run:    use docker-compose instead (see docker-compose.yml)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1 — Build dependencies with UV inside a slim builder
# ---------------------------------------------------------------------------
FROM python:3.10-slim AS builder

# Prevents Python from writing .pyc files and enables unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install UV (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first (maximises Docker layer cache hits)
COPY pyproject.toml uv.lock ./

# Install all project dependencies into a dedicated virtual environment
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2 — Lean production image
# ---------------------------------------------------------------------------
FROM python:3.10-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Tell Python to use the venv created by the builder stage
    PATH="/app/.venv/bin:$PATH"

# Install only the runtime system dependency needed by psycopg2-binary
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pre-built virtualenv from the builder (no pip install at runtime)
COPY --from=builder /app/.venv /app/.venv

# Copy the full project source code
COPY . .

# Create a non-root user for security
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app

USER appuser

# Expose the Django development server port
EXPOSE 8000

# Entrypoint: waits for DB, runs migrations, optionally seeds, then starts server
ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
