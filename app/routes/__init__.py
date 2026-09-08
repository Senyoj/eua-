from app.routes.alerts import router as alerts_router
from app.routes.feeding import router as feeding_router
from app.routes.readings import router as readings_router
from app.routes.robot import router as robot_router
from app.routes.settings import router as settings_router
from app.routes.telemetry import router as telemetry_router

__all__ = [
    "readings_router",
    "robot_router",
    "feeding_router",
    "alerts_router",
    "settings_router",
    "telemetry_router",
]
