"""Validate and normalise uploaded images."""
import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageValidationError(ValueError):
    pass


def load_image(data: bytes, max_bytes: int, max_pixels: int) -> Image.Image:
    """Return an RGB, EXIF-oriented PIL image or raise ImageValidationError."""
    if not data:
        raise ImageValidationError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ImageValidationError(f"Image is too large (limit {max_bytes // (1024 * 1024)} MB).")
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        width, height = probe.size
        if fmt not in ALLOWED_FORMATS:
            raise ImageValidationError("Unsupported image type. Use JPEG, PNG or WebP.")
        if width * height > max_pixels:
            raise ImageValidationError("Image dimensions are too large.")
        probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ImageValidationError("The file is not a valid image.")
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def save_product_image(data: bytes, directory: Path, max_bytes: int, max_pixels: int,
                       max_side: int = 1600) -> str:
    """Validate, re-encode as JPEG (strips metadata) and store under a random name.

    The client-supplied file name is never used, which prevents path traversal.
    Returns the stored file name.
    """
    img = load_image(data, max_bytes, max_pixels)
    img.thumbnail((max_side, max_side))
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    img.save(directory / name, format="JPEG", quality=88, optimize=True)
    return name


def delete_stored_image(directory: Path, name: str) -> None:
    """Delete a stored file, refusing anything that is not a plain file name."""
    if not name or Path(name).name != name:
        return
    target = directory / name
    try:
        if target.is_file() and target.resolve().parent == directory.resolve():
            target.unlink()
    except OSError:
        pass
