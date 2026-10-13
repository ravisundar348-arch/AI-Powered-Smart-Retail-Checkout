"""Detection + classification service wrapping the notebook pipeline.

Pipeline (same two stages as Detect_Classify_Bill.ipynb):
  YOLOv8m localises regions -> filter boxes -> MobileNetV2 classifies each crop.

Deliberate corrections vs. the notebook (see README, "Findings"):
  * crops are fed as RGB (the notebook fed OpenCV's BGR);
  * MobileNetV2 `preprocess_input` is applied, matching Model_Training.ipynb
    (the notebook divided by 255, which the model was never trained on);
  * the filtered detections are the ones classified (the notebook computed
    them and then classified the unfiltered list).

None of this can claim accuracy: the trained weights are not in the repository
and this service has NOT been run against them by the author of this code.
"""
import base64
import io
import logging
import threading
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..config import settings
from .ai_postprocess import prepare_crop, remove_contained_boxes, remove_nested_boxes

log = logging.getLogger("smart_retail.ai")


class RecognitionService:
    def __init__(self):
        self._lock = threading.Lock()
        self._yolo = None
        self._cnn = None
        self._preprocess = None
        self.load_error: str | None = None
        self.loaded = False

    # ------------------------------------------------------------------ loading
    def load(self) -> None:
        """Load both models once at start-up. Never raises; records why on failure."""
        self.loaded = False
        if not settings.ai_enabled:
            self.load_error = "AI is disabled (SMART_AI_ENABLED=0)."
            return
        missing = [str(p) for p in (settings.keras_model_path, settings.yolo_model_path) if not Path(p).is_file()]
        if missing:
            self.load_error = "Model file(s) not found: " + ", ".join(missing)
            log.warning(self.load_error)
            return
        try:
            from ultralytics import YOLO
            from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
            from tensorflow.keras.models import load_model

            self._yolo = YOLO(str(settings.yolo_model_path))
            self._cnn = load_model(str(settings.keras_model_path))
            self._preprocess = preprocess_input
            out = int(self._cnn.output_shape[-1])
            if out != len(settings.class_names):
                raise RuntimeError(
                    f"Classifier outputs {out} classes but {len(settings.class_names)} class names "
                    "are configured (SMART_CLASS_NAMES)."
                )
            self.loaded, self.load_error = True, None
            log.info("AI models loaded.")
        except Exception as exc:  # noqa: BLE001 - report any import/model problem
            self._yolo = self._cnn = None
            self.load_error = f"Could not load AI models: {exc}"
            log.error(self.load_error)

    def status(self) -> dict:
        return {
            "available": self.loaded,
            "reason": None if self.loaded else self.load_error,
            "classes": settings.class_names,
            "confidence_threshold": settings.cnn_confidence_threshold,
            "note": ("Recognition identifies product CLASSES. It cannot tell pack sizes/variants "
                     "apart unless the classifier was trained on them; the cashier confirms the SKU."),
        }

    # ---------------------------------------------------------------- inference
    def analyze(self, pil_rgb: Image.Image) -> list:
        if not self.loaded:
            raise RuntimeError(self.load_error or "AI models are not loaded.")
        rgb = np.asarray(pil_rgb.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        with self._lock:
            results = self._yolo(bgr, conf=settings.yolo_confidence, verbose=False)
            dets = []
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                    dets.append({"bbox": (x1, y1, x2, y2), "confidence": float(box.conf[0])})
            dets = remove_contained_boxes(remove_nested_boxes(dets))
            dets.sort(key=lambda d: d["confidence"], reverse=True)
            dets = dets[: settings.max_detections]

            crops, kept = [], []
            for d in dets:
                crop = prepare_crop(rgb, d["bbox"])
                if crop is not None:
                    crops.append(crop)
                    kept.append(d)
            if not crops:
                return []
            batch = self._preprocess(np.stack(crops).astype("float32"))
            probs = self._cnn.predict(batch, verbose=0)

        out = []
        names = settings.class_names
        for i, (d, p, crop) in enumerate(zip(kept, probs, crops)):
            order = np.argsort(p)[::-1][:3]
            best = int(order[0])
            out.append({
                "index": i,
                "bbox": list(d["bbox"]),
                "detector_confidence": round(d["confidence"], 4),
                "ai_class": names[best],
                "confidence": round(float(p[best]), 4),
                "top_k": [{"ai_class": names[int(k)], "confidence": round(float(p[int(k)]), 4)} for k in order],
                "thumbnail": _thumb_data_url(crop),
            })
        return out


def _thumb_data_url(rgb_crop: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgb_crop).resize((112, 112)).save(buf, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


recognition = RecognitionService()
