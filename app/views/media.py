from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
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

PUBLIC_MEDIA_PREFIXES = (
    "public/",
    "profile_pictures/",
    "profile_banners/",
    "shortcut_icons/",
    "avatar_characters/",
)


def _resolve_media_path(source):
    try:
        resolved = Path(safe_join(settings.MEDIA_ROOT, source)).resolve()
    except ValueError as exc:
        raise Http404 from exc

    media_root = Path(settings.MEDIA_ROOT).resolve()
    if not resolved.is_file() or media_root not in resolved.parents:
        raise Http404

    return resolved


def _authenticated_user(request):
    user = getattr(request, "user", None)
    return user if getattr(user, "is_authenticated", False) else None


def _user_can_access_gallery(user, source):
    from ..models import ProfileGalleryImage, UserBlock

    image = ProfileGalleryImage.objects.select_related("user").filter(image=source).first()
    if not image:
        return False
    if user and image.user_id == user.id:
        return True
    if not image.is_public:
        return False
    if not user:
        return True
    return not UserBlock.objects.filter(
        Q(blocker=user, blocked=image.user) | Q(blocker=image.user, blocked=user)
    ).exists()


def _user_can_access_chat_media(user, source):
    if not user:
        return False

    from ..models import ChatAttachment, ChatRoom

    if source.startswith(("private/chat_attachments/", "chat_attachments/")):
        return ChatAttachment.objects.filter(
            file=source,
            message__room__room_memberships__user=user,
        ).exists()

    if source.startswith("chat_group_avatars/"):
        return ChatRoom.objects.filter(
            avatar=source,
            room_memberships__user=user,
        ).exists()

    return False


def _user_can_access_clock_sound(user, source):
    if not user:
        return False

    from ..models import ClockSettings

    return ClockSettings.objects.filter(user=user, custom_sound=source).exists()


def _ensure_thumbnail_source_allowed(request, source):
    normalized_source = str(source or "").replace("\\", "/")
    if normalized_source.startswith(PUBLIC_MEDIA_PREFIXES):
        return

    user = _authenticated_user(request)

    if normalized_source.startswith("profile_gallery/") and _user_can_access_gallery(user, normalized_source):
        return

    if _user_can_access_chat_media(user, normalized_source):
        return

    if normalized_source.startswith(("private/clock_sounds/", "clock_sounds/")) and _user_can_access_clock_sound(user, normalized_source):
        return

    if normalized_source.startswith(("private/file_shares/", "file_shares/", "_thumbs/")):
        raise Http404

    raise PermissionDenied


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
    _ensure_thumbnail_source_allowed(request, source)
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
