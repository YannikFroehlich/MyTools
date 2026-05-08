from django.db import models


class ShortcutSection(models.Model):
    name = models.CharField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Shortcut(models.Model):
    section = models.ForeignKey(
        ShortcutSection,
        on_delete=models.CASCADE,
        related_name="shortcuts",
        null=True,
        blank=True
    )

    name = models.CharField(max_length=50)
    url = models.URLField()
    icon = models.CharField(
        max_length=80,
        default="fa-solid fa-link",
        help_text="FontAwesome Icon-Klasse, z.B. fa-brands fa-youtube"
    )

    image = models.ImageField(
        upload_to="shortcut_icons/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name