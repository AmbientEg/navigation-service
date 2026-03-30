"""Routes module - exports all route handlers."""

from . import buildings_routes
from . import floors_routes
from . import graph_routes
from . import navigation_routes

__all__ = [
    'buildings_routes',
    'floors_routes',
    'graph_routes',
    'navigation_routes',
]
