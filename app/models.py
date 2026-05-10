from django.db import models


class ShortcutSection(models.Model):
    COLOR_CHOICES = [
        ("blue", "Blau"),
        ("green", "Grün"),
        ("purple", "Lila"),
        ("orange", "Orange"),
        ("red", "Rot"),
    ]

    name = models.CharField(max_length=60)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default="blue")
    order = models.PositiveIntegerField(default=0)
    is_collapsed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]

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

    is_favorite = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.name


class AvatarCharacter(models.Model):
    NATION_CHOICES = [
        ("Feuer", "Feuernation"),
        ("Wasser", "Wasserstamm"),
        ("Erde", "Erdkönigreich"),
        ("Luft", "Luftnomaden"),
    ]

    name = models.CharField(max_length=80)
    nation = models.CharField(max_length=20, choices=NATION_CHOICES)
    link = models.URLField(blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="avatar_characters/")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        image_storage = self.image.storage if self.image else None
        image_name = self.image.name if self.image else None

        super().delete(*args, **kwargs)

        if image_storage and image_name:
            image_storage.delete(image_name)
