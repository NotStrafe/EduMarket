from fastapi import FastAPI

from app.api.routes import courses, enrollments, orders, reports, reviews, users, imports
from app.core.config import settings
from app.db.init_db import init_db


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    register_events(app)
    register_healthcheck(app)
    register_routes(app)
    return app


def register_healthcheck(app: FastAPI) -> None:
    @app.get("/api/health", summary="Health check")
    async def healthcheck() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        }


def register_events(app: FastAPI) -> None:
    @app.on_event("startup")
    async def on_startup() -> None:
        await init_db()


def register_routes(app: FastAPI) -> None:
    app.include_router(users.router, prefix="/api")
    app.include_router(courses.router, prefix="/api")
    app.include_router(enrollments.router, prefix="/api")
    app.include_router(orders.router, prefix="/api")
    app.include_router(reviews.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(imports.router, prefix="/api")


app = create_application()
