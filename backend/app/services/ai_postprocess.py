"""Pure helper functions extracted from Detect_Classify_Bill.ipynb.

Kept free of TensorFlow / Ultralytics imports so they can be unit-tested
without the heavy AI stack.
"""
import cv2
import numpy as np


def box_area(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


def calculate_iou(a, b):
    """Intersection-over-union (notebook version, plus a zero-division guard)."""
    xa, ya = max(a[0], b[0]), max(a[1], b[1])
    xb, yb = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    union = box_area(a) + box_area(b) - inter
    return inter / float(union) if union > 0 else 0.0


def remove_nested_boxes(detections, iou_threshold=0.7):
    """Original notebook logic: drop a box if it overlaps a larger one with IoU > threshold."""
    to_remove = set()
    for i, di in enumerate(detections):
        for j, dj in enumerate(detections):
            if i == j:
                continue
            if calculate_iou(di["bbox"], dj["bbox"]) > iou_threshold and \
                    box_area(di["bbox"]) < box_area(dj["bbox"]):
                to_remove.add(i)
                break
    return [d for k, d in enumerate(detections) if k not in to_remove]


def remove_contained_boxes(detections, containment_threshold=0.9):
    """ADDITION (not in the notebook): drop a box that lies >= threshold inside a larger box.

    IoU alone cannot catch a small box fully inside a big one, which is what
    "nested" really means; this keeps one box per physical item more reliably.
    """
    keep = []
    for i, di in enumerate(detections):
        a = di["bbox"]
        area_i = box_area(a)
        contained = False
        for j, dj in enumerate(detections):
            if i == j:
                continue
            b = dj["bbox"]
            if box_area(b) <= area_i:
                continue
            xa, ya = max(a[0], b[0]), max(a[1], b[1])
            xb, yb = min(a[2], b[2]), min(a[3], b[3])
            inter = max(0, xb - xa) * max(0, yb - ya)
            if area_i > 0 and inter / area_i >= containment_threshold:
                contained = True
                break
        if not contained:
            keep.append(di)
    return keep


def clip_box(box, width, height):
    x1, y1, x2, y2 = box
    return (max(0, min(width, x1)), max(0, min(height, y1)),
            max(0, min(width, x2)), max(0, min(height, y2)))


def make_square_with_padding(image):
    """Pad a crop to a white square (notebook behaviour)."""
    h, w = image.shape[:2]
    side = max(h, w)
    canvas = np.full((side, side, 3), 255, dtype=np.uint8)
    y0, x0 = (side - h) // 2, (side - w) // 2
    canvas[y0:y0 + h, x0:x0 + w] = image
    return canvas


def prepare_crop(rgb_image, bbox, size=224):
    """Crop (RGB array), pad to square and resize. Returns uint8 RGB or None if empty."""
    h, w = rgb_image.shape[:2]
    x1, y1, x2, y2 = clip_box(bbox, w, h)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    crop = rgb_image[y1:y2, x1:x2]
    return cv2.resize(make_square_with_padding(crop), (size, size))
