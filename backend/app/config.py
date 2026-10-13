"""Application configuration, read from environment variables (.env supported).

Nothing secret lives in source code. If SMART_SECRET_KEY is not set, an
ephemeral random key is generated at start-up (sessions end on restart).
"""
import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

log = logging.getLogger("smart_retail.config")

DEFAULT_CLASSES = [
    "Amul_Ice_Cream", "Cake", "CeraVe", "HnS_Shampoo",
    "Nestle_Milk_Powder", "Plum", "Thums_Up", "Wild_Stone",
]  # alphabetical = Keras flow_from_directory index order used in training


def _path(env: str, default: Path) -> Path:
    raw = os.environ.get(env)
    p = Path(raw) if raw else default
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def _int(env: str, default: int) -> int:
    try:
        return int(os.environ.get(env, default))
    except ValueError:
        return default


def _float(env: str, default: float) -> float:
    try:
        return float(os.environ.get(env, default))
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        key = os.environ.get("SMART_SECRET_KEY", "").strip()
        if len(key) < 32:
            if key:
                log.warning("SMART_SECRET_KEY is shorter than 32 chars; using an ephemeral key.")
            else:
                log.warning("SMART_SECRET_KEY not set; using an ephemeral key (logins reset on restart).")
            key = secrets.token_urlsafe(48)
        self.secret_key = key
        self.access_token_minutes = _int("SMART_TOKEN_MINUTES", 480)

        data_dir = BACKEND_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.database_url = os.environ.get(
            "SMART_DATABASE_URL", f"sqlite:///{(data_dir / 'smart_retail.db').as_posix()}"
        )
        self.storage_dir = _path("SMART_STORAGE_DIR", BACKEND_DIR / "storage")
        self.product_media_dir = self.storage_dir / "products"
        self.frontend_dir = PROJECT_ROOT / "frontend"

        origins = os.environ.get("SMART_CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
        self.cors_origins = [o.strip() for o in origins.split(",") if o.strip()]

        self.max_upload_bytes = _int("SMART_MAX_UPLOAD_MB", 8) * 1024 * 1024
        self.max_image_pixels = _int("SMART_MAX_IMAGE_MEGAPIXELS", 40) * 1_000_000

        # AI artifacts (see README: these are NOT shipped in the GitHub repo)
        self.keras_model_path = _path("SMART_KERAS_MODEL", PROJECT_ROOT / "full_model.keras")
        self.yolo_model_path = _path("SMART_YOLO_MODEL", PROJECT_ROOT / "yolov8m.pt")
        classes = os.environ.get("SMART_CLASS_NAMES")
        self.class_names = [c.strip() for c in classes.split(",")] if classes else list(DEFAULT_CLASSES)
        self.cnn_confidence_threshold = _float("SMART_CNN_CONFIDENCE", 0.8)  # original notebook value
        self.yolo_confidence = _float("SMART_YOLO_CONFIDENCE", 0.25)  # ultralytics default
        self.max_detections = _int("SMART_MAX_DETECTIONS", 40)
        self.ai_enabled = os.environ.get("SMART_AI_ENABLED", "1") != "0"

        self.shop_name = os.environ.get("SMART_SHOP_NAME", "Smart Retail Checkout")
        self.shop_address = os.environ.get("SMART_SHOP_ADDRESS", "")
        self.timezone = os.environ.get("SMART_TIMEZONE", "Asia/Kolkata")
        self.offers_file = _path("SMART_OFFERS_FILE", BACKEND_DIR / "app" / "data" / "offers.json")


settings = Settings()
