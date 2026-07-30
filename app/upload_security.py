from dataclasses import dataclass
from pathlib import Path

from django.core.files import File
from django.utils.text import get_valid_filename
from PIL import Image, UnidentifiedImageError

from .image_optimization import optimize_uploaded_image


SAFE_IMAGE_CONTENT_TYPE = "image/webp"
ATTACHMENT_CONTENT_TYPE = "application/octet-stream"


@dataclass(frozen=True)
class PreparedUpload:
    file: File
    stored_filename: str
    display_name: str
    content_type: str
    size: int


def prepare_untrusted_upload(
    uploaded_file,
    *,
    prefix: str,
    max_image_size: tuple[int, int],
    quality: int = 82,
    target_bytes: int | None = None,
) -> PreparedUpload:
    """Normalize declared raster images and make every other upload inert.

    Browser supplied MIME types are only used to decide whether an image
    decode should be attempted. Only a successful Pillow decode followed by a
    fresh WebP encode is considered safe for inline display.
    """
    original_name = get_valid_filename(Path(uploaded_file.name).name)[:180] or "datei"
    declared_type = (getattr(uploaded_file, "content_type", "") or "").lower()

    if declared_type.startswith("image/"):
        try:
            optimized = optimize_uploaded_image(
                uploaded_file,
                prefix=prefix,
                max_size=max_image_size,
                quality=quality,
                target_bytes=target_bytes,
            )
        except Image.DecompressionBombError:
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)
            raise
        except (UnidentifiedImageError, OSError, ValueError):
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)
        else:
            display_name = f"{Path(original_name).stem or 'bild'}.webp"
            return PreparedUpload(
                file=optimized.file,
                stored_filename=optimized.filename,
                display_name=display_name,
                content_type=SAFE_IMAGE_CONTENT_TYPE,
                size=optimized.file.size,
            )

    return PreparedUpload(
        file=uploaded_file,
        stored_filename=original_name,
        display_name=original_name,
        content_type=ATTACHMENT_CONTENT_TYPE,
        size=uploaded_file.size,
    )
