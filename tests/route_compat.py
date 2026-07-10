from __future__ import annotations

from typing import Any


def route_contexts(router: Any) -> list[Any]:
    """Return effective routes on legacy and router-tree FastAPI releases."""

    routes = list(getattr(router, "routes", ()))
    try:
        from fastapi.routing import iter_route_contexts
    except ImportError:  # FastAPI < 0.137
        return routes
    return list(iter_route_contexts(routes))


def route_paths(router: Any) -> set[str]:
    """Return the concrete route paths exposed by a FastAPI app or router."""

    return {
        str(route.path)
        for route in route_contexts(router)
        if getattr(route, "path", None) is not None
    }
