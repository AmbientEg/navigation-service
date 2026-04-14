#!/bin/bash
# Docker entrypoint script for Navigation Service
# Provides dynamic initialization based on environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Wait for database to be ready
wait_for_db() {
    log "Waiting for database at ${DATABASE_HOST:-db}:${DATABASE_PORT:-5432}..."

    until PGPASSWORD="${DATABASE_PASSWORD:-postgres}" psql -h "${DATABASE_HOST:-db}" -U "${DATABASE_USER:-postgres}" -c '\q' 2>/dev/null; do
        warn "Database is unavailable - sleeping"
        sleep 1
    done

    log "Database is up!"
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."

    if [ -d "migrations" ]; then
        for file in migrations/*.sql; do
            if [ -f "$file" ]; then
                log "Applying migration: $file"
                PGPASSWORD="${DATABASE_PASSWORD:-postgres}" psql \
                    -h "${DATABASE_HOST:-db}" \
                    -U "${DATABASE_USER:-postgres}" \
                    -d "${DATABASE_NAME:-navigation}" \
                    -f "$file" || warn "Migration $file may have already been applied"
            fi
        done
    fi

    log "Migrations complete!"
}

# Initialize database with SQLAlchemy
create_tables() {
    log "Creating tables with SQLAlchemy..."
    python -c "
import asyncio
import sys
sys.path.insert(0, '/app')
from database import db_manager
from models import Base

async def init():
    await db_manager.initialize()
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await db_manager.close()
    print('Tables created successfully!')

asyncio.run(init())
"
}

# Main execution
case "${1:-api}" in
    api)
        log "Starting Navigation API Server..."

        # Wait for database
        wait_for_db

        # Run migrations if requested
        if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
            run_migrations
        fi

        # Create tables
        if [ "${CREATE_TABLES:-true}" = "true" ]; then
            create_tables
        fi

        # Start the server based on environment
        if [ "${ENVIRONMENT:-development}" = "development" ]; then
            log "Starting in DEVELOPMENT mode with hot reload..."
            exec python -m uvicorn main:app \
                --host "${HOST:-0.0.0.0}" \
                --port "${PORT:-8000}" \
                --reload \
                --reload-dir . \
                --log-level "${LOG_LEVEL:-debug}"
        else
            log "Starting in PRODUCTION mode..."
            exec python -m uvicorn main:app \
                --host "${HOST:-0.0.0.0}" \
                --port "${PORT:-8000}" \
                --workers "${WORKERS:-4}" \
                --log-level "${LOG_LEVEL:-info}"
        fi
        ;;

    migrate)
        log "Running migrations..."
        wait_for_db
        run_migrations
        create_tables
        log "Migrations complete!"
        ;;

    test)
        log "Running tests..."
        wait_for_db
        create_tables
        exec pytest tests/ -v "$@"
        ;;

    shell)
        log "Starting shell..."
        exec /bin/bash
        ;;

    *)
        log "Executing: $@"
        exec "$@"
        ;;
esac
