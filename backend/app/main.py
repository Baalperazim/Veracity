from fastapi import FastAPI

from app.api.routes.assets import router as assets_router
from app.api.routes.health import router as health_router
from app.api.routes.tokenization import router as tokenization_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(health_router)
app.include_router(assets_router)
app.include_router(tokenization_router)
