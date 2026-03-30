"""Integration-specific pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from database import get_db_session
from main import app


@pytest.fixture
def client():
    """Shared TestClient for integration tests."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_db_session_dependency(mock_db_session):
    """Provide a mocked DB session for every integration test request."""

    async def _override_get_db_session():
        yield mock_db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture(autouse=True)
def disable_http_middlewares_for_integration_tests():
    """Use a minimal middleware stack to keep endpoint error responses deterministic in tests."""
    original_user_middleware = list(app.user_middleware)
    app.user_middleware = []
    app.middleware_stack = app.build_middleware_stack()
    try:
        yield
    finally:
        app.user_middleware = original_user_middleware
        app.middleware_stack = app.build_middleware_stack()
