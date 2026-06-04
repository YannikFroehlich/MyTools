import io
import uuid
from dataclasses import dataclass

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


@dataclass(frozen=True)
class OptimizedImageResult:
    file: ContentFile
    filename: str


PROFILE_AVATAR_MAX_SIZE = (512, 512)
PROFILE_BANNER_MAX_SIZE = (1600, 520)
GALLERY_IMAGE_MAX_SIZE = (1600, 1600)


def _safe_webp_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)

    if image.mode in ("RGBA", "LA"):
        return image.convert("RGBA")

    if image.mode == "P":
        if "transparency" in image.info:
            return image.convert("RGBA")
        return image.convert("RGB")

    if image.mode not in ("RGB", "RGBA"):
        return image.convert("RGB")

    return image


def _resize_to_fit(image: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    if image.width <= max_size[0] and image.height <= max_size[1]:
        return image

    resized = image.copy()
    resized.thumbnail(max_size, Image.Resampling.LANCZOS)
    return resized


def _save_webp(image: Image.Image, *, quality: int, target_bytes: int | None) -> bytes:
    quality = max(45, min(90, quality))
    min_quality = 50
    last_data = b""

    while quality >= min_quality:
        buffer = io.BytesIO()
        save_kwargs = {
            "format": "WEBP",
            "quality": quality,
            "method": 6,
            "optimize": True,
        }

        if image.mode == "RGBA":
            save_kwargs["lossless"] = False
            save_kwargs["exact"] = False

        image.save(buffer, **save_kwargs)
        last_data = buffer.getvalue()

        if not target_bytes or len(last_data) <= target_bytes:
            return last_data

        quality -= 8

    return last_data


def optimize_uploaded_image(uploaded_file, *, prefix: str, max_size: tuple[int, int], quality: int = 82, target_bytes: int | None = None) -> OptimizedImageResult:
    """Resize and compress an uploaded image to WebP before it is stored.

    This keeps profile/media uploads small and fast to serve without needing
    expensive processing on every page load.
    """
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    try:
        with Image.open(uploaded_file) as source:
            image = _safe_webp_image(source)
            image = _resize_to_fit(image, max_size)
            data = _save_webp(image, quality=quality, target_bytes=target_bytes)
    except (UnidentifiedImageError, OSError, ValueError):
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        raise

    filename = f"{prefix}_{uuid.uuid4().hex}.webp"
    return OptimizedImageResult(ContentFile(data), filename)
