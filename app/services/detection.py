"""
DolphinID — Detection service (YOLO-World wrapper).

Handles loading YOLO-World and detecting dorsal fins in images.
"""
import logging
from pathlib import Path

import cv2
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded singleton
_yolo_model = None


def _get_yolo_model():
    """Load YOLO-World model (lazy singleton)."""
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLOWorld
        weights_path = settings.yolo_weights
        if not weights_path.exists():
            raise FileNotFoundError(f"YOLO weights not found: {weights_path}")
        logger.info(f"Loading YOLO-World from {weights_path}...")
        _yolo_model = YOLOWorld(str(weights_path))
        _yolo_model.set_classes(settings.yolo_classes)
        logger.info("YOLO-World loaded successfully.")
    return _yolo_model


def unload_yolo() -> None:
    """Explicitly unload YOLO model to free VRAM."""
    global _yolo_model
    if _yolo_model is not None:
        del _yolo_model
        _yolo_model = None
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("YOLO-World unloaded.")


def detect_and_crop(
    image_path: Path,
    output_dir: Path,
    confidence: float | None = None,
    padding: int | None = None,
) -> list[dict]:
    """
    Detect dorsal fins in an image and save crops.

    Args:
        image_path: Path to the input image
        output_dir: Directory to save crop images
        confidence: YOLO confidence threshold (default from settings)
        padding: Padding around bounding box in pixels (default from settings)

    Returns:
        List of detection results, each with:
          - crop_path: Path to saved crop
          - confidence: YOLO confidence score
          - bbox: (x, y, w, h)
    """
    conf = confidence or settings.yolo_confidence
    pad = padding or settings.yolo_crop_padding

    model = _get_yolo_model()
    results = model.predict(str(image_path), conf=conf, verbose=False)
    result = results[0]

    if len(result.boxes) == 0:
        return []

    original_img = cv2.imread(str(image_path))
    if original_img is None:
        raise ValueError(f"Could not read image: {image_path}")

    h_img, w_img = original_img.shape[:2]
    detections = []

    # Sort by confidence, process all detections
    sorted_boxes = sorted(result.boxes, key=lambda x: x.conf[0], reverse=True)

    output_dir.mkdir(parents=True, exist_ok=True)

    for crop_idx, box in enumerate(sorted_boxes):
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf_score = float(box.conf[0])

        # Apply padding
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w_img, x2 + pad)
        y2 = min(h_img, y2 + pad)

        crop = original_img[y1:y2, x1:x2]
        crop_name = f"{image_path.stem}_crop_{crop_idx}.jpg"
        crop_path = output_dir / crop_name
        cv2.imwrite(str(crop_path), crop)

        detections.append({
            "crop_path": str(crop_path),
            "crop_index": crop_idx,
            "confidence": conf_score,
            "bbox": (x1, y1, x2 - x1, y2 - y1),
        })

    return detections
