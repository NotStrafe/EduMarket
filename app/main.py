from fastapi import FastAPI

from app.core.config import settings


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    register_healthcheck(app)
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


app = create_application()
