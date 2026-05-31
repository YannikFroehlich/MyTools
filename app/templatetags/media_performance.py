from django import template
from django.urls import reverse
from urllib.parse import urlencode

register = template.Library()


@register.filter
def media_thumb(file_field, spec):
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
