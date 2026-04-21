from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import uvicorn
import logging
import os
import sys
from datetime import datetime
from contextlib import asynccontextmanager

from models import Base
# Database
from database import db_manager

# Routes
from routes import buildings_routes, floors_routes, graph_routes, navigation_routes
try:
    import routes.poi_routes as poi_routes
except ImportError:
    poi_routes = None

# ----------------------------------------------------
# Production Logging Configuration
# ----------------------------------------------------
def setup_logging():
    """Configure production-ready logging with proper formatting and levels."""
    # Determine log level based on environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set specific logger levels for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logging.getLogger(__name__)


logger = setup_logging()


# ----------------------------------------------------
# Lifespan for Startup & Shutdown
# ----------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and AI services on startup, cleanup on shutdown"""
    try:
        # Startup tasks
        await db_manager.initialize()
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized and tables created successfully")

        # Yield control to FastAPI (application runs)
        yield

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    finally:
        # Shutdown tasks
        try:
            await db_manager.close()
            logger.info("✅ Database connections closed")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        logger.info("Application shutdown completed")


# ----------------------------------------------------
# Production FastAPI App Configuration
# ----------------------------------------------------
# Determine if running in production (Lambda/AWS)
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"

app = FastAPI(
    title="Indoor Navigation API",
    description="Navigation Service",
    version="1.0.0",
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url="/redoc" if not IS_PRODUCTION else None,
    openapi_url="/openapi.json" if not IS_PRODUCTION else None,
    lifespan=lifespan if not IS_LAMBDA else None,
    generate_unique_id_function=lambda route: f"{route.tags[0]}-{route.name}" if route.tags else route.name,
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "tryItOutEnabled": True,
        "persistAuthorization": True,
    }
)

# Include routers immediately after app creation
app.include_router(navigation_routes.router, prefix="/api/navigation", tags=["Navigation"])
app.include_router(buildings_routes.router, prefix="/api/buildings", tags=["Buildings"])
app.include_router(floors_routes.router, prefix="/api/floors", tags=["Floors"])
app.include_router(graph_routes.router, prefix="/api/graphs", tags=["Graphs"])
if poi_routes:
    app.include_router(poi_routes.router, prefix="/api/pois", tags=["POI"])



# ----------------------------------------------------
# Production Middleware Stack
# ----------------------------------------------------

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)

    # Skip security headers for docs in development
    if not IS_PRODUCTION and request.url.path in ["/docs", "/redoc", "/openapi.json"]:
        return response

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    # Add correlation ID if present
    correlation_id = getattr(request.state, 'correlation_id', None)
    if correlation_id:
        response.headers["X-Correlation-ID"] = correlation_id

    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests for monitoring."""
    start_time = datetime.utcnow()

    # Generate correlation ID for request tracing
    correlation_id = request.headers.get("X-Correlation-ID", f"req_{start_time.timestamp()}")
    request.state.correlation_id = correlation_id

    logger.info(
        f"Incoming request - Method: {request.method}, "
        f"URL: {request.url}, "
        f"Client IP: {request.client.host if request.client else 'unknown'}, "
        f"Correlation ID: {correlation_id}"
    )

    response = await call_next(request)
    process_time = (datetime.utcnow() - start_time).total_seconds()

    logger.info(
        f"Request completed - Status: {response.status_code}, "
        f"Duration: {process_time:.3f}s, "
        f"Correlation ID: {correlation_id}"
    )

    return response


# Trusted Host Middleware (for production)
if IS_PRODUCTION:
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")
    if allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# CORS Configuration
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Correlation-ID",
        "X-Requested-With",
    ],
    expose_headers=["X-Correlation-ID"],
)


# ----------------------------------------------------
# Production Exception Handlers
# ----------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging and response format."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.warning(
        f"HTTP Exception - Status: {exc.status_code}, "
        f"Detail: {exc.detail}, "
        f"Path: {request.url.path}, "
        f"Correlation ID: {correlation_id}"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
            "correlation_id": correlation_id,
            "type": "http_error"
        }
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Map malformed JSON payload errors to 400 while keeping other validation as 422."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    errors = jsonable_encoder(exc.errors())
    is_json_parse_error = any(err.get("type") == "json_invalid" for err in errors)
    status_code = 400 if is_json_parse_error else 422

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": errors,
            "error": "Malformed JSON" if is_json_parse_error else "Validation failed",
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
            "correlation_id": correlation_id,
            "type": "validation_error",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with proper logging."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.error(
        f"Unhandled exception - Type: {type(exc).__name__}, "
        f"Message: {str(exc)}, "
        f"Path: {request.url.path}, "
        f"Correlation ID: {correlation_id}",
        exc_info=True
    )

    # Don't expose internal error details in production
    error_detail = "Internal server error" if IS_PRODUCTION else str(exc)

    return JSONResponse(
        status_code=500,
        content={
            "detail": error_detail,
            "error": error_detail,
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
            "correlation_id": correlation_id,
            "type": "internal_error"
        }
    )


# ----------------------------------------------------
# Production Health and Monitoring Endpoints
# ----------------------------------------------------
@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint for load balancers and monitoring."""
    try:
        # Check database connectivity
        db_healthy = True
        try:
            if not IS_LAMBDA:  # Skip DB check in Lambda cold starts
                async with db_manager.engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_healthy = False

        # Overall health status
        overall_status = "healthy" if db_healthy else "degraded"

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "unknown"),
            "checks": {
                "database": "healthy" if db_healthy else "unhealthy",
                "api": "healthy"
            },
            "lambda": IS_LAMBDA,
            "production": IS_PRODUCTION
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Health check failed"
            }
        )


@app.get("/health/ready")
async def readiness_check():
    """Readiness probe for Kubernetes/container orchestration."""
    try:
        # More thorough checks for readiness
        if not IS_LAMBDA:
            async with db_manager.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))

        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "error": str(e)}
        )


@app.get("/health/live")
async def liveness_check():
    """Liveness probe for Kubernetes/container orchestration."""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@app.get("/")
async def root():
    return {
        "message": "Indoor Navigation API",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/health",
        "endpoints": {
            "buildings": "/api/buildings",
            "floors": "/api/floors",
            "graphs": "/api/graphs",
            "navigation": "/api/navigation"
        }
    }


@app.get("/api/status")
async def get_api_status():
    return {
        "api_status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "building_management": True,
            "floor_geojson_management": True,
            "graph_rebuild_preview": True,
            "graph_confirm_versioning": True,
            "graph_rollback": True,
            "route_calculation": True
        },
        "routing": {
            "algorithm": "networkx_shortest_path",
            "source_of_truth": "floors.floor_geojson",
            "uses_active_graph_version": True
        }
    }


# Run Server
# ----------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        log_level="info"

    )