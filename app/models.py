from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(
        upload_to="profile_pictures/",
        null=True,
        blank=True,
        verbose_name="Profilbild",
    )
    bio = models.TextField(
        max_length=500,
        blank=True,
        verbose_name="Über mich",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profile"

    def __str__(self):
        return f"Profil von {self.user.username}"

    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return ""

    @property
    def initials(self):
        first_name = (self.user.first_name or "").strip()
        last_name = (self.user.last_name or "").strip()

        if first_name or last_name:
            return f"{first_name[:1]}{last_name[:1]}".upper()

        return (self.user.username[:2] or "MT").upper()


class ShortcutSection(models.Model):
    COLOR_CHOICES = [
        ("blue", "Blau"),
        ("green", "Grün"),
        ("purple", "Lila"),
        ("orange", "Orange"),
        ("red", "Rot"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shortcut_sections",
        null=True,
        blank=True,
    )
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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shortcuts",
        null=True,
        blank=True,
    )
    section = models.ForeignKey(
        ShortcutSection,
        on_delete=models.CASCADE,
        related_name="shortcuts",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=50)
    url = models.URLField()
    icon = models.CharField(
        max_length=80,
        default="fa-solid fa-link",
        help_text="FontAwesome Icon-Klasse, z.B. fa-brands fa-youtube",
    )

    image = models.ImageField(
        upload_to="shortcut_icons/",
        null=True,
        blank=True,
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

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="avatar_characters",
        null=True,
        blank=True,
    )
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


class Note(models.Model):
    COLOR_CHOICES = [
        ("blue", "Blau"),
        ("purple", "Lila"),
        ("green", "Grün"),
        ("orange", "Orange"),
        ("red", "Rot"),
        ("gray", "Grau"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=120, blank=True)
    content = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True)

    color = models.CharField(
        max_length=20,
        choices=COLOR_CHOICES,
        default="blue",
    )

    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-updated_at"]
        verbose_name = "Notiz"
        verbose_name_plural = "Notizen"

    def __str__(self):
        return self.title or "Unbenannte Notiz"

    def tag_list(self):
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]


class WeatherLocation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weather_locations",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "Wetter-Ort"
        verbose_name_plural = "Wetter-Orte"
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_weather_location_per_user"),
        ]

    def __str__(self):
        return self.name




class HomeWidget(models.Model):
    WIDGET_WEATHER = "weather"
    WIDGET_NOTES = "notes"
    WIDGET_BENCHMARK = "benchmark"
    WIDGET_STATS = "stats"

    WIDGET_CHOICES = [
        (WIDGET_WEATHER, "Wetter"),
        (WIDGET_NOTES, "Notizen"),
        (WIDGET_BENCHMARK, "Human Benchmark"),
        (WIDGET_STATS, "Schnellstatistiken"),
    ]

    COLOR_CHOICES = [
        ("blue", "Blau"),
        ("green", "Grün"),
        ("purple", "Lila"),
        ("orange", "Orange"),
        ("red", "Rot"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="home_widgets",
    )
    title = models.CharField(max_length=80)
    widget_type = models.CharField(max_length=30, choices=WIDGET_CHOICES, default=WIDGET_WEATHER)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default="blue")
    weather_location = models.ForeignKey(
        WeatherLocation,
        on_delete=models.SET_NULL,
        related_name="home_widgets",
        null=True,
        blank=True,
    )
    order = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["user", "order", "created_at"]),
        ]
        verbose_name = "Home-Widget"
        verbose_name_plural = "Home-Widgets"

    def __str__(self):
        return f"{self.title} · {self.get_widget_type_display()}"

class HumanBenchmarkScore(models.Model):
    GAME_REACTION = "reaction"
    GAME_AIM = "aim"
    GAME_TYPING = "typing"
    GAME_VISUAL = "visual"

    GAME_CHOICES = [
        (GAME_REACTION, "Reaktion"),
        (GAME_AIM, "Aim Trainer"),
        (GAME_TYPING, "Typing Test"),
        (GAME_VISUAL, "Visual Memory"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="human_benchmark_scores",
    )
    game = models.CharField(max_length=20, choices=GAME_CHOICES)
    score = models.FloatField()
    display_score = models.CharField(max_length=80)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "game", "-created_at"]),
            models.Index(fields=["game", "score"]),
        ]
        verbose_name = "Human Benchmark Ergebnis"
        verbose_name_plural = "Human Benchmark Ergebnisse"

    def __str__(self):
        return f"{self.user} · {self.get_game_display()} · {self.display_score}"


class HumanBenchmarkHighScore(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="human_benchmark_highscores",
    )
    game = models.CharField(max_length=20, choices=HumanBenchmarkScore.GAME_CHOICES)
    score = models.FloatField()
    display_score = models.CharField(max_length=80)
    details = models.JSONField(default=dict, blank=True)
    achieved_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "game"],
                name="unique_human_benchmark_highscore_per_user_game",
            ),
        ]
        indexes = [
            models.Index(fields=["game", "score"]),
        ]
        verbose_name = "Human Benchmark Highscore"
        verbose_name_plural = "Human Benchmark Highscores"

    def __str__(self):
        return f"{self.user} · {self.get_game_display()} · {self.display_score}"