from django import template
from django.urls import reverse
from urllib.parse import urlencode

register = template.Library()


def _media_thumb_url(file_field, spec):
    if not file_field:
        return ""

    name = getattr(file_field, "name", "")
    if not name:
        return ""

    url = reverse("media_thumbnail", kwargs={"spec": spec, "source": name})
    try:
        modified = file_field.storage.get_modified_time(name)
        return f"{url}?{urlencode({'v': int(modified.timestamp())})}"
    except (OSError, ValueError):
        return url


@register.filter
def media_thumb(file_field, spec):
    return _media_thumb_url(file_field, spec)


@register.filter
def media_srcset(file_field, specs):
    """Build a responsive srcset from thumbnail specs.

    Template usage:
        {{ profile.avatar|media_srcset:'avatar-small 96w, avatar 192w' }}
    """
    entries = []

    for raw_entry in str(specs or "").split(","):
        parts = raw_entry.strip().split()
        if not parts:
            continue

        spec = parts[0]
        descriptor = parts[1] if len(parts) > 1 else ""
        url = _media_thumb_url(file_field, spec)

        if not url:
            continue

        entries.append(f"{url} {descriptor}".strip())

    return ", ".join(entries)
