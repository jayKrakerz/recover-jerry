"""FastAPI application factory."""

import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .api.router import api_router

# Configure logging for our modules
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")
logging.getLogger("recover_jerry").setLevel(logging.DEBUG)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Disable caching for JS/CSS files during development."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.endswith(('.js', '.css')):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="recover-jerry",
        version="0.1.0",
        description="macOS data recovery tool",
    )

    app.add_middleware(NoCacheStaticMiddleware)
    app.include_router(api_router, prefix="/api")

    if settings.frontend_dir.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(settings.frontend_dir), html=True),
            name="frontend",
        )

    return app
