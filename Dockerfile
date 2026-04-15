# =============================================================================
# Builder Stage
# =============================================================================
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# =============================================================================
# Robust apt strategy (FIXED HASH SUM / MIRROR SAFE)
# =============================================================================
RUN set -eux && \ 
    rm -rf /var/lib/apt/lists/* &&\
    apt-get clean &&\
    apt-get update --fix-missing &&\
    apt-get install -y --no-install-recommends build-essential &&\
    rm -rf /var/lib/apt/lists/* &&\
    find /usr/local -type d -name "__pycache__" -exec rm -r {} + || true

# Copy dependencies first (better caching)
COPY requirements.txt .

# Install Python deps into isolated prefix
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================================================
# Production Stage
# =============================================================================
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH"

WORKDIR /app

# Create non-root user early (best practice)
RUN useradd -m appuser

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Fix permissions
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Production command (NO reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]