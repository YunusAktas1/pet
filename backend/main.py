from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import settings
from backend.core.db import init_db
from backend.core.errors import install_exception_handlers
from backend.core.response import ok
from backend.routers import auth, matches, messages, pairs, pets, photos


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialize DB (create engine/session, etc.)
    init_db()
    yield


app = FastAPI(
    title="PetMatch API",
    lifespan=lifespan,
)

# --- CORS ---
# Dev'de permissive olabilir; prod'da settings.CORS_ORIGINS ile sýnýrla
# settings içinde CORS_ORIGINS yoksa "*" kullanýr.
origins = getattr(settings, "CORS_ORIGINS", None) or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception handlers (standard error envelope) ---
install_exception_handlers(app)

# --- Media (static) ---
media_path = Path(settings.MEDIA_DIR)
media_path.mkdir(parents=True, exist_ok=True)
app.mount(
    settings.MEDIA_BASE_URL,
    StaticFiles(directory=str(media_path)),
    name="media",
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/healthz")
def healthz() -> dict:
    # Minimum health check (DB ping is optional; we can add after seeing db.py)
    return {"ok": True}


# --- API v1 routers ---
app.include_router(auth.router, prefix=settings.api_v1_str)
app.include_router(pets.router, prefix=settings.api_v1_str)
app.include_router(matches.router, prefix=settings.api_v1_str)
app.include_router(pairs.router, prefix=settings.api_v1_str)
app.include_router(messages.router, prefix=settings.api_v1_str)
app.include_router(photos.router, prefix=settings.api_v1_str)
