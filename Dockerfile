# =============================================================================
# Development Stage
# =============================================================================
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# it works and creates an image if size ~ 700mb with this layer
# this give Hash Sum mismatch
RUN rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    apt-get update --fix-missing && \
    apt-get install -y build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================================================
# Production Stage
# =============================================================================
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy only installed packages
COPY --from=builder /install /usr/local

# Copy app code
COPY . .

# Create non-root user
RUN useradd -m appuser
USER appuser

EXPOSE 8000

# Production command (NO reload ❗)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
