import logging
import json
from fastapi import Request
from fastapi.responses import RedirectResponse

from fastapi.exceptions import ValidationException
import uvicorn
from fastapi import FastAPI
from fastapi_sqlalchemy import DBSessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.core.router import router
from app.models import Base
from app.core.database import engine
from app.core.config import settings
from app.utils.exception_handler import (
    CustomException,
    fastapi_error_handler,
    validation_exception_handler,
    custom_error_handler,
)

logging.config.fileConfig(settings.LOGGING_CONFIG_FILE, disable_existing_loggers=False)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logging.warning(f"Chưa kết nối được Database trên {settings.DATABASE_URL}: {e}")


def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        docs_url="/docs",
        redoc_url="/re-docs",
        openapi_url=f"{settings.API_PREFIX}/openapi.json",
        description="""
        Base frame with FastAPI micro framework + Postgresql
            - Login/Register with JWT
            - Permission
            - CRUD User
            - Unit testing with Pytest
            - Dockerize
        """,
        debug=settings.DEBUG,
        swagger_ui_init_oauth={
            "clientId": settings.KEYCLOAK_CLIENT_ID,
            "scopes": {"openid": "OpenID Connect scope"},
        },
        swagger_ui_parameters={
            "docExpansion": "none",
        },
    )
    origins = settings.BACKEND_CORS_ORIGINS
    if isinstance(origins, str):
        try:
            origins = json.loads(origins)
        except ValueError:
            origins = [value.strip() for value in origins.split(",") if value.strip()]
    if not isinstance(origins, list):
        origins = []
    origins = list(dict.fromkeys([*origins, "http://localhost:8010", "http://127.0.0.1:8010"]))
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(DBSessionMiddleware, db_url=settings.DATABASE_URL)
    application.include_router(router, prefix=settings.API_PREFIX)
    @application.get("/frontend/{path:path}", include_in_schema=False)
    def primary_portal(request: Request, path: str):
        # One frontend origin; its real-run API stays on the control service.
        hostname = request.url.hostname or "localhost"
        return RedirectResponse(f"{request.url.scheme}://{hostname}:8010/frontend/{path}")

    application.add_exception_handler(CustomException, custom_error_handler)
    application.add_exception_handler(ValidationException, validation_exception_handler)
    application.add_exception_handler(Exception, fastapi_error_handler)

    return application


app = get_application()
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=settings.DEBUG)
