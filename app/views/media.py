from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils._os import safe_join
from django.utils.http import http_date
from django.views.decorators.http import require_GET
from PIL import Image, ImageOps, UnidentifiedImageError


THUMBNAIL_SPECS = {
    "avatar-tiny": (48, 48, "cover"),
    "avatar-small": (96, 96, "cover"),
    "avatar": (192, 192, "cover"),
    "avatar-large": (384, 384, "cover"),
    "banner-small": (720, 236, "cover"),
    "banner": (1280, 420, "cover"),
    "banner-large": (1920, 630, "cover"),
    "gallery-small": (320, 320, "cover"),
    "gallery": (640, 640, "cover"),
    "gallery-large": (960, 960, "cover"),
    "preview-small": (480, 360, "contain"),
    "preview": (960, 720, "contain"),
    "shortcut-small": (64, 64, "contain"),
    "shortcut": (128, 128, "contain"),
}


def _resolve_media_path(source):
    try:
        resolved = Path(safe_join(settings.MEDIA_ROOT, source)).resolve()
    except ValueError as exc:
        raise Http404 from exc

    media_root = Path(settings.MEDIA_ROOT).resolve()
    if not resolved.is_file() or media_root not in resolved.parents:
        raise Http404

    return resolved


def _thumbnail_path(source, spec, original_path):
    source_path = Path(source)
    # Thumbnails are always delivered as WebP. That keeps transparent avatars intact,
    # but avoids repeatedly serving larger PNG/JPEG previews in cards and menus.
    thumb_name = f"{source_path.stem}-{spec}.webp"
    return Path(settings.MEDIA_ROOT) / "_thumbs" / spec / source_path.parent / thumb_name


def _has_transparency(image):
    if image.mode in {"RGBA", "LA"}:
        return True
    return image.mode == "P" and "transparency" in image.info


def _thumbnail_needs_refresh(original_path, thumb_path):
    if not thumb_path.exists():
        return True

    if thumb_path.stat().st_mtime < original_path.stat().st_mtime:
        return True

    try:
        with Image.open(original_path) as original, Image.open(thumb_path) as thumb:
            return _has_transparency(original) and not _has_transparency(thumb)
    except (OSError, UnidentifiedImageError):
        return True


def _generate_thumbnail(original_path, thumb_path, spec):
    width, height, mode = THUMBNAIL_SPECS[spec]
    thumb_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(original_path) as image:
        image = ImageOps.exif_transpose(image)
        if _has_transparency(image):
            image = image.convert("RGBA")

        if mode == "cover":
            image = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
        else:
            image.thumbnail((width, height), Image.Resampling.LANCZOS)

        save_kwargs = {"optimize": True, "quality": 82, "method": 6}
        if image.mode not in {"RGBA", "LA"}:
            image = image.convert("RGB")

        image.save(thumb_path, "WEBP", **save_kwargs)


@require_GET
def media_thumbnail(request, spec, source):
    if spec not in THUMBNAIL_SPECS:
        raise Http404

    original_path = _resolve_media_path(source)
    thumb_path = _thumbnail_path(source, spec, original_path)

    try:
        if _thumbnail_needs_refresh(original_path, thumb_path):
            _generate_thumbnail(original_path, thumb_path, spec)
    except (OSError, UnidentifiedImageError) as exc:
        raise Http404 from exc

    stat = thumb_path.stat()
    last_modified = http_date(stat.st_mtime)
    if request.headers.get("If-Modified-Since") == last_modified:
        return HttpResponseNotModified()

    response = FileResponse(thumb_path.open("rb"), content_type="image/webp")
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["Last-Modified"] = last_modified
    return response
