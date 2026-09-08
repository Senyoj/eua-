from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import Settings, get_settings
from app.core.security import verify_api_key
from app.routes import (
    alerts_router,
    feeding_router,
    readings_router,
    robot_router,
    settings_router,
    telemetry_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_application() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(readings_router)
    application.include_router(robot_router)
    application.include_router(feeding_router)
    application.include_router(alerts_router)
    application.include_router(settings_router)
    application.include_router(telemetry_router)

    @application.get(
        "/health",
        status_code=status.HTTP_200_OK,
        tags=["Health"],
    )
    def health_check(settings: Settings = Depends(get_settings)):
        return {
            "status": "healthy",
            "environment": settings.ENVIRONMENT,
            "version": settings.VERSION,
        }

    @application.get(
        "/api/protected-ping",
        status_code=status.HTTP_200_OK,
        tags=["Security"],
    )
    def protected_ping(api_key: str = Depends(verify_api_key)):
        return {
            "status": "authenticated",
            "message": "API Key successfully validated",
        }

    return application


app = create_application()
