from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Product, User
from ..services.ai_service import recognition
from ..services.catalog import product_out
from ..services.image_validation import ImageValidationError, load_image

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.get("/status")
def scan_status(_: User = Depends(current_user)):
    return recognition.status()


@router.post("")
def scan_image(file: UploadFile = File(...), db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Runs detection + classification on one image.

    If the AI models are unavailable this returns `ai_available: false` with the reason and NO
    detections. It never fabricates a result; the cashier adds items manually instead.
    """
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"Image is too large (limit {settings.max_upload_bytes // (1024 * 1024)} MB).")
    try:
        image = load_image(data, settings.max_upload_bytes, settings.max_image_pixels)
    except ImageValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    if not recognition.loaded:
        return {"ai_available": False, "reason": recognition.load_error, "image_size": list(image.size),
                "detections": []}
    try:
        raw = recognition.analyze(image)
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "Image analysis failed. You can add items manually.")

    classes = {d["ai_class"] for d in raw}
    by_class: dict = {}
    if classes:
        for p in db.scalars(select(Product).where(Product.ai_class.in_(classes), Product.is_active.is_(True))):
            by_class.setdefault(p.ai_class, []).append(product_out(p))

    detections = []
    for d in raw:
        candidates = by_class.get(d["ai_class"], [])
        confident = d["confidence"] >= settings.cnn_confidence_threshold
        # A detection is only auto-acceptable when confident AND exactly one SKU maps to the class.
        match = "unique" if len(candidates) == 1 else ("ambiguous" if candidates else "none")
        detections.append({**d, "candidates": candidates, "match": match,
                           "needs_review": (not confident) or match != "unique"})
    return {"ai_available": True, "reason": None, "image_size": list(image.size), "detections": detections,
            "confidence_threshold": settings.cnn_confidence_threshold}
