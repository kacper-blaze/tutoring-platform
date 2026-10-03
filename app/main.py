"""
Punkt wejścia aplikacji - System zarządzania platformą korepetycji online.

Spina routery wszystkich pięciu modułów pod wspólnym prefiksem /api/v1
(konwencja wersjonowania, sekcja 3.9).
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import Base, engine
from app.core.exceptions import AppError
from app.modules.admin.api.routes import router as admin_router
from app.modules.booking.api.routes import router as booking_router
from app.modules.catalog.api.routes import router as catalog_router
from app.modules.planning.api.routes import router as planning_router
from app.modules.users.api.auth_routes import router as auth_router
from app.modules.users.api.users_routes import router as users_router

# Import modeli, żeby Base.metadata "widziała" wszystkie tabele przy create_all/Alembic.
from app.modules.admin.domain import models as admin_models  # noqa: F401
from app.modules.booking.domain import models as booking_models  # noqa: F401
from app.modules.catalog.domain import models as catalog_models  # noqa: F401
from app.modules.planning.domain import models as planning_models  # noqa: F401
from app.modules.users.domain import models as users_models  # noqa: F401

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "API systemu zarządzania platformą korepetycji online - wszystkie pięć "
        "modułów ze specyfikacji (Użytkownicy, Katalog, Planowanie, Rezerwacje, "
        "Administracja) zaimplementowanych w architekturze modularnego monolitu."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    body = {"error": exc.error_code, "message": exc.message}
    if exc.details:
        body["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Mapuje błędy walidacji Pydantic na format VALIDATION_FAILED z sekcji 3.9."""
    details = [
        {"field": ".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][-1]), "code": err["type"], "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "VALIDATION_FAILED", "details": details},
    )


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


# --- Rejestracja routerów modułów pod /api/v1 ---------------------------

app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(users_router, prefix=settings.api_v1_prefix)
app.include_router(catalog_router, prefix=settings.api_v1_prefix)
app.include_router(planning_router, prefix=settings.api_v1_prefix)
app.include_router(booking_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def on_startup() -> None:
    """
    Tworzy tabele przy starcie, jeśli jeszcze nie istnieją.

    W środowisku produkcyjnym docelowo należy zarządzać schematem
    wyłącznie przez migracje Alembic (katalog alembic/) - create_all()
    jest wygodne dla szybkiego developmentu/demo.
    """
    if settings.environment == "development":
        Base.metadata.create_all(bind=engine)
