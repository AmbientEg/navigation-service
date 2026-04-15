# Multi-stage Dockerfile for Navigation Service
# Using Ubuntu 24.04 LTS for better compatibility with scientific Python packages

# =============================================================================
# Base Stage - Common dependencies
# =============================================================================
FROM ubuntu:24.04 AS base

# Build arguments
ARG APP_USER=appuser
ARG APP_GROUP=appgroup
ARG APP_UID=1000
ARG APP_GID=1000

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies with retry and cache bypass
RUN rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 -o Acquire::http::Timeout=30 \
        python3.12 \
        python3.12-dev \
        python3-pip \
        python3.12-venv \
        build-essential \
        libpq-dev \
        gdal-bin \
        libgdal-dev \
        postgresql-client \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g ${APP_GID} ${APP_GROUP} && \
    useradd -u ${APP_UID} -g ${APP_GROUP} -m -s /bin/bash ${APP_USER}

WORKDIR /app

# Upgrade pip and install wheel
RUN python3.12 -m pip install --upgrade pip setuptools wheel

# Copy requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Development Stage
# =============================================================================
FROM base AS development

ARG APP_USER=appuser

# Install development dependencies
COPY requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements-test.txt

# Install additional dev tools
RUN apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends \
        git \
        vim \
        htop \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY --chown=${APP_USER}:${APP_USER} . .

# Copy and set up entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER ${APP_USER}

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["api"]

# =============================================================================
# Builder Stage - Optimized Python packages
# =============================================================================
FROM base AS builder

# Install production dependencies in user site-packages
COPY requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

# =============================================================================
# Production Stage
# =============================================================================
FROM ubuntu:24.04 AS production

ARG APP_USER=appuser
ARG APP_GROUP=appgroup
ARG APP_UID=1000
ARG APP_GID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    APP_HOME=/app \
    PATH="/home/${APP_USER}/.local/bin:${PATH}"

# Install only runtime dependencies with retry logic and cache bypass
RUN rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    apt-get update -o Acquire::Check-Valid-Until=false && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=5 -o Acquire::http::Timeout=30 \
        python3.12 \
        libpq5 \
        gdal-bin \
        libgdal-dev \
        postgresql-client \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g ${APP_GID} ${APP_GROUP} && \
    useradd -u ${APP_UID} -g ${APP_GROUP} -m -s /bin/bash ${APP_USER}

WORKDIR ${APP_HOME}

# Copy Python packages from builder
COPY --from=builder --chown=${APP_USER}:${APP_GROUP} /root/.local /home/${APP_USER}/.local

# Copy application code
COPY --chown=${APP_USER}:${APP_GROUP} . ${APP_HOME}

# Copy and set up entrypoint
COPY --chown=${APP_USER}:${APP_GROUP} docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER ${APP_USER}

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["api"]

# =============================================================================
# Test Stage
# =============================================================================
FROM base AS test

ARG APP_USER=appuser

COPY requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements-test.txt

COPY --chown=${APP_USER}:${APP_USER} . .

USER ${APP_USER}

CMD ["pytest", "tests/", "-v"]