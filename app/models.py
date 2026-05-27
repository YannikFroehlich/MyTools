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



def clock_sound_upload_path(instance, filename):
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp3"
    return f"clock_sounds/user_{instance.user_id}/custom_timer_sound.{suffix}"


def validate_clock_sound_size(file):
    from django.core.exceptions import ValidationError

    max_size = 5 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError("Der eigene Klingelton darf maximal 5 MB groß sein.")


class ClockWorldCity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clock_world_cities",
    )
    label = models.CharField(max_length=80)
    timezone = models.CharField(max_length=80)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["user", "order", "created_at"]),
        ]
        verbose_name = "Weltuhr-Ort"
        verbose_name_plural = "Weltuhr-Orte"

    def __str__(self):
        return f"{self.label} · {self.timezone}"


class ClockTimerPreset(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clock_timer_presets",
    )
    name = models.CharField(max_length=80)
    hours = models.PositiveSmallIntegerField(default=0)
    minutes = models.PositiveSmallIntegerField(default=0)
    seconds = models.PositiveSmallIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["user", "order", "created_at"]),
        ]
        verbose_name = "Timer-Vorlage"
        verbose_name_plural = "Timer-Vorlagen"

    def __str__(self):
        return self.name

    @property
    def total_seconds(self):
        return (self.hours * 3600) + (self.minutes * 60) + self.seconds

    @property
    def display_duration(self):
        parts = []
        if self.hours:
            parts.append(f"{self.hours} h")
        if self.minutes:
            parts.append(f"{self.minutes} min")
        if self.seconds:
            parts.append(f"{self.seconds} s")
        return " ".join(parts) or "0 s"


class ClockSettings(models.Model):
    RINGTONE_BELL = "bell"
    RINGTONE_CHIME = "chime"
    RINGTONE_DIGITAL = "digital"
    RINGTONE_SOFT = "soft"
    RINGTONE_ALARM = "alarm"
    RINGTONE_CUSTOM = "custom"

    RINGTONE_CHOICES = [
        (RINGTONE_BELL, "Bell"),
        (RINGTONE_CHIME, "Chime"),
        (RINGTONE_DIGITAL, "Digital"),
        (RINGTONE_SOFT, "Soft"),
        (RINGTONE_ALARM, "Alarm"),
        (RINGTONE_CUSTOM, "Eigener Ton"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clock_settings",
    )
    volume = models.PositiveSmallIntegerField(default=80)
    ringtone = models.CharField(max_length=20, choices=RINGTONE_CHOICES, default=RINGTONE_BELL)
    custom_sound = models.FileField(
        upload_to=clock_sound_upload_path,
        validators=[validate_clock_sound_size],
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Uhr-Einstellung"
        verbose_name_plural = "Uhr-Einstellungen"

    def __str__(self):
        return f"Uhr-Einstellungen von {self.user}"

    @property
    def custom_sound_url(self):
        if self.custom_sound:
            return self.custom_sound.url
        return ""

    def save(self, *args, **kwargs):
        old_sound_name = None
        if self.pk:
            old_sound_name = (
                ClockSettings.objects
                .filter(pk=self.pk)
                .values_list("custom_sound", flat=True)
                .first()
            )

        super().save(*args, **kwargs)

        if old_sound_name and self.custom_sound and old_sound_name != self.custom_sound.name:
            self.custom_sound.storage.delete(old_sound_name)

    def delete(self, *args, **kwargs):
        sound_storage = self.custom_sound.storage if self.custom_sound else None
        sound_name = self.custom_sound.name if self.custom_sound else None

        super().delete(*args, **kwargs)

        if sound_storage and sound_name:
            sound_storage.delete(sound_name)


class HomeWidget(models.Model):
    WIDGET_WEATHER = "weather"
    WIDGET_NOTES = "notes"
    WIDGET_BENCHMARK = "benchmark"
    WIDGET_STATS = "stats"
    WIDGET_CLOCK = "clock"

    WIDGET_CHOICES = [
        (WIDGET_WEATHER, "Wetter"),
        (WIDGET_NOTES, "Notizen"),
        (WIDGET_BENCHMARK, "Human Benchmark"),
        (WIDGET_STATS, "Schnellstatistiken"),
        (WIDGET_CLOCK, "Uhr"),
    ]

    CLOCK_DESIGN_MINIMAL = "minimal"
    CLOCK_DESIGN_GLASS = "glass"
    CLOCK_DESIGN_NEON = "neon"
    CLOCK_DESIGN_FLIP = "flip"
    CLOCK_DESIGN_TERMINAL = "terminal"

    CLOCK_DESIGN_CHOICES = [
        (CLOCK_DESIGN_MINIMAL, "Minimal"),
        (CLOCK_DESIGN_GLASS, "Glass"),
        (CLOCK_DESIGN_NEON, "Neon"),
        (CLOCK_DESIGN_FLIP, "Flip"),
        (CLOCK_DESIGN_TERMINAL, "Terminal"),
    ]

    CLOCK_STYLE_CLASSIC = "classic"
    CLOCK_STYLE_COMPACT = "compact"
    CLOCK_STYLE_SPLIT = "split"
    CLOCK_STYLE_ANALOG = "analog"
    CLOCK_STYLE_HYBRID = "hybrid"

    CLOCK_STYLE_CHOICES = [
        (CLOCK_STYLE_CLASSIC, "Klassisch"),
        (CLOCK_STYLE_COMPACT, "Kompakt"),
        (CLOCK_STYLE_SPLIT, "Datum links"),
        (CLOCK_STYLE_ANALOG, "Analog"),
        (CLOCK_STYLE_HYBRID, "Analog + Digital"),
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
    clock_design = models.CharField(
        max_length=20,
        choices=CLOCK_DESIGN_CHOICES,
        default=CLOCK_DESIGN_MINIMAL,
    )
    clock_style = models.CharField(
        max_length=20,
        choices=CLOCK_STYLE_CHOICES,
        default=CLOCK_STYLE_CLASSIC,
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


class HomeLayoutPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="home_layout_preference",
    )
    widget_area_order = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Home-Layout-Einstellung"
        verbose_name_plural = "Home-Layout-Einstellungen"

    def __str__(self):
        return f"Home-Layout von {self.user}"


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