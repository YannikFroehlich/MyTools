from django import template
from django.urls import reverse

register = template.Library()


@register.filter
def media_thumb(file_field, spec):
    if not file_field:
        return ""

    name = getattr(file_field, "name", "")
    if not name:
        return ""

    return reverse("media_thumbnail", kwargs={"spec": spec, "source": name})
