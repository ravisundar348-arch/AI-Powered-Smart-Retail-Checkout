import logging
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import auth, bills, dashboard, products, scan
from .services.ai_service import recognition

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smart_retail")

# Windows can map .js/.css to text/plain via the registry, which browsers then refuse to run.
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings.product_media_dir.mkdir(parents=True, exist_ok=True)
    recognition.load()  # loads models ONCE; records a reason if unavailable
    yield


app = FastAPI(title="Smart Retail Checkout API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # explicit list from SMART_CORS_ORIGINS; never "*"
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)  # details stay in the server log only
    return JSONResponse({"detail": "Something went wrong on the server. Please try again."}, status_code=500)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "ai_available": recognition.loaded}


for r in (auth.router, products.router, scan.router, bills.router, dashboard.router):
    app.include_router(r)

settings.product_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/products", StaticFiles(directory=str(settings.product_media_dir)), name="media")
if settings.frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")
