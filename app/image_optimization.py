import io
import os
import uuid
from dataclasses import dataclass

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


@dataclass(frozen=True)
class OptimizedImageResult:
    file: ContentFile
    filename: str


@dataclass(frozen=True)
class ExistingImageOptimizationResult:
    converted: bool
    skipped: bool
    missing: bool
    old_name: str
    new_name: str
    old_size: int
    new_size: int
    bytes_saved: int
    reason: str = ""


PROFILE_AVATAR_MAX_SIZE = (512, 512)
GALLERY_IMAGE_MAX_SIZE = (1600, 1600)
SHORTCUT_ICON_MAX_SIZE = (512, 512)
CHAT_AVATAR_MAX_SIZE = (512, 512)
WIKI_IMAGE_MAX_SIZE = (1200, 1200)
FILE_SHARE_IMAGE_MAX_SIZE = (1600, 1600)


WEBP_EXTENSION = ".webp"


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


def _convert_image_file(file_obj, *, max_size: tuple[int, int], quality: int, target_bytes: int | None) -> bytes:
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)

    with Image.open(file_obj) as source:
        image = _safe_webp_image(source)
        image = _resize_to_fit(image, max_size)
        return _save_webp(image, quality=quality, target_bytes=target_bytes)


def optimize_uploaded_image(uploaded_file, *, prefix: str, max_size: tuple[int, int], quality: int = 82, target_bytes: int | None = None) -> OptimizedImageResult:
    """Resize and compress an uploaded image to WebP before it is stored.

    This keeps profile/media uploads small and fast to serve without needing
    expensive processing on every page load.
    """
    try:
        data = _convert_image_file(uploaded_file, max_size=max_size, quality=quality, target_bytes=target_bytes)
    except (UnidentifiedImageError, OSError, ValueError):
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        raise

    filename = f"{prefix}_{uuid.uuid4().hex}.webp"
    return OptimizedImageResult(ContentFile(data), filename)


def _candidate_webp_name(old_name: str) -> str:
    directory, filename = os.path.split(old_name)
    stem = os.path.splitext(filename)[0] or "image"
    new_filename = f"{stem}_{uuid.uuid4().hex[:10]}{WEBP_EXTENSION}"
    return os.path.join(directory, new_filename) if directory else new_filename


def optimize_existing_image_field(instance, field_name: str, *, max_size: tuple[int, int], quality: int = 82, target_bytes: int | None = None, extra_update_fields: dict | None = None) -> ExistingImageOptimizationResult:
    """Convert an already stored ImageField/FileField image to a smaller WebP file.

    The database pointer is updated only after the new file was saved. The old
    file is deleted afterwards so the media folder actually frees disk space.
    """
    file_field = getattr(instance, field_name, None)
    old_name = getattr(file_field, "name", "") or ""
    if not old_name:
        return ExistingImageOptimizationResult(False, True, False, "", "", 0, 0, 0, "empty")

    storage = file_field.storage
    if not storage.exists(old_name):
        return ExistingImageOptimizationResult(False, False, True, old_name, old_name, 0, 0, 0, "missing")

    old_size = storage.size(old_name)
    try:
        with storage.open(old_name, "rb") as source:
            data = _convert_image_file(source, max_size=max_size, quality=quality, target_bytes=target_bytes)
    except (UnidentifiedImageError, OSError, ValueError):
        return ExistingImageOptimizationResult(False, True, False, old_name, old_name, old_size, old_size, 0, "unsupported")

    if old_name.lower().endswith(WEBP_EXTENSION) and len(data) >= old_size:
        return ExistingImageOptimizationResult(False, True, False, old_name, old_name, old_size, old_size, 0, "already_optimized")

    new_name = storage.save(_candidate_webp_name(old_name), ContentFile(data))
    setattr(instance, field_name, new_name)

    update_fields = [field_name]
    if extra_update_fields:
        for attr, value in extra_update_fields.items():
            setattr(instance, attr, value)
            update_fields.append(attr)

    instance.save(update_fields=update_fields)

    if old_name != new_name:
        storage.delete(old_name)

    new_size = storage.size(new_name)
    return ExistingImageOptimizationResult(
        True,
        False,
        False,
        old_name,
        new_name,
        old_size,
        new_size,
        max(old_size - new_size, 0),
    )


def optimize_static_image_path(path, *, max_size: tuple[int, int], quality: int = 78, target_bytes: int | None = None) -> ExistingImageOptimizationResult:
    """Re-compress a static image file in place when this can be done safely.

    Static CSS/template references must keep working after the optimization. For
    that reason this helper only overwrites files that already have the .webp
    extension. Other formats are skipped instead of silently changing the file
    content while the URL still ends with .png/.jpg.
    """
    path = os.fspath(path)
    old_name = os.path.basename(path)

    if not os.path.exists(path):
        return ExistingImageOptimizationResult(False, False, True, old_name, old_name, 0, 0, 0, "missing")

    old_size = os.path.getsize(path)
    if not path.lower().endswith(WEBP_EXTENSION):
        return ExistingImageOptimizationResult(False, True, False, old_name, old_name, old_size, old_size, 0, "static_not_webp")

    try:
        with open(path, "rb") as source:
            data = _convert_image_file(source, max_size=max_size, quality=quality, target_bytes=target_bytes)
    except (UnidentifiedImageError, OSError, ValueError):
        return ExistingImageOptimizationResult(False, True, False, old_name, old_name, old_size, old_size, 0, "unsupported")

    if len(data) >= old_size:
        return ExistingImageOptimizationResult(False, True, False, old_name, old_name, old_size, old_size, 0, "already_optimized")

    tmp_path = f"{path}.tmp"
    with open(tmp_path, "wb") as target:
        target.write(data)
    os.replace(tmp_path, path)

    new_size = os.path.getsize(path)
    return ExistingImageOptimizationResult(
        True,
        False,
        False,
        old_name,
        old_name,
        old_size,
        new_size,
        max(old_size - new_size, 0),
    )
