from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


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
    profile_banner = models.ImageField(
        upload_to="profile_banners/",
        null=True,
        blank=True,
        verbose_name="Profilbanner",
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


class Friendship(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Ausstehend")),
        (STATUS_ACCEPTED, _("Befreundet")),
    ]

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_friendships",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_friendships",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Freundschaft"
        verbose_name_plural = "Freundschaften"
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                name="unique_friendship_request_direction",
            ),
            models.CheckConstraint(
                condition=~models.Q(from_user=models.F("to_user")),
                name="friendship_prevent_self_request",
            ),
        ]
        indexes = [
            models.Index(fields=["from_user", "status"]),
            models.Index(fields=["to_user", "status"]),
        ]

    def __str__(self):
        return f"{self.from_user} → {self.to_user} · {self.get_status_display()}"

    def other_user(self, user):
        if self.from_user_id == user.id:
            return self.to_user
        if self.to_user_id == user.id:
            return self.from_user
        return None

    @classmethod
    def between(cls, user_a, user_b):
        return cls.objects.filter(
            models.Q(from_user=user_a, to_user=user_b)
            | models.Q(from_user=user_b, to_user=user_a)
        ).first()

    @classmethod
    def accepted_for_user(cls, user):
        return cls.objects.select_related("from_user", "to_user").filter(
            status=cls.STATUS_ACCEPTED
        ).filter(
            models.Q(from_user=user) | models.Q(to_user=user)
        )

    @classmethod
    def friend_ids_for_user(cls, user):
        friendships = cls.accepted_for_user(user).values_list("from_user_id", "to_user_id")
        return [to_id if from_id == user.id else from_id for from_id, to_id in friendships]


class ShortcutSection(models.Model):
    COLOR_CHOICES = [
        ("blue", _("Blau")),
        ("green", _("Grün")),
        ("purple", _("Lila")),
        ("orange", _("Orange")),
        ("red", _("Rot")),
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
        ("blue", _("Blau")),
        ("purple", _("Lila")),
        ("green", _("Grün")),
        ("orange", _("Orange")),
        ("red", _("Rot")),
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
        (WIDGET_WEATHER, _("Wetter")),
        (WIDGET_NOTES, _("Notizen")),
        (WIDGET_BENCHMARK, _("Human Benchmark")),
        (WIDGET_STATS, _("Schnellstatistiken")),
        (WIDGET_CLOCK, _("Uhr")),
    ]

    CLOCK_DESIGN_MINIMAL = "minimal"
    CLOCK_DESIGN_GLASS = "glass"
    CLOCK_DESIGN_NEON = "neon"
    CLOCK_DESIGN_FLIP = "flip"
    CLOCK_DESIGN_TERMINAL = "terminal"

    CLOCK_DESIGN_CHOICES = [
        (CLOCK_DESIGN_MINIMAL, _("Minimal")),
        (CLOCK_DESIGN_GLASS, _("Glass")),
        (CLOCK_DESIGN_NEON, _("Neon")),
        (CLOCK_DESIGN_FLIP, _("Flip")),
        (CLOCK_DESIGN_TERMINAL, _("Terminal")),
    ]

    CLOCK_STYLE_CLASSIC = "classic"
    CLOCK_STYLE_COMPACT = "compact"
    CLOCK_STYLE_SPLIT = "split"
    CLOCK_STYLE_ANALOG = "analog"
    CLOCK_STYLE_HYBRID = "hybrid"

    CLOCK_STYLE_CHOICES = [
        (CLOCK_STYLE_CLASSIC, _("Klassisch")),
        (CLOCK_STYLE_COMPACT, _("Kompakt")),
        (CLOCK_STYLE_SPLIT, _("Datum links")),
        (CLOCK_STYLE_ANALOG, _("Analog")),
        (CLOCK_STYLE_HYBRID, _("Analog + Digital")),
    ]

    WEATHER_DESIGN_CLEAN = "clean"
    WEATHER_DESIGN_GLASS = "glass"
    WEATHER_DESIGN_AURORA = "aurora"
    WEATHER_DESIGN_SUNSET = "sunset"
    WEATHER_DESIGN_NIGHT = "night"

    WEATHER_DESIGN_CHOICES = [
        (WEATHER_DESIGN_CLEAN, _("Clean")),
        (WEATHER_DESIGN_GLASS, _("Glass")),
        (WEATHER_DESIGN_AURORA, _("Aurora")),
        (WEATHER_DESIGN_SUNSET, _("Sunset")),
        (WEATHER_DESIGN_NIGHT, _("Night")),
    ]

    WEATHER_STYLE_CLASSIC = "classic"
    WEATHER_STYLE_HERO = "hero"
    WEATHER_STYLE_COMPACT = "compact"
    WEATHER_STYLE_SPLIT = "split"

    WEATHER_STYLE_CHOICES = [
        (WEATHER_STYLE_CLASSIC, _("Klassisch")),
        (WEATHER_STYLE_HERO, _("Groß")),
        (WEATHER_STYLE_COMPACT, _("Kompakt")),
        (WEATHER_STYLE_SPLIT, _("Geteilt")),
    ]

    COLOR_CHOICES = [
        ("blue", _("Blau")),
        ("green", _("Grün")),
        ("purple", _("Lila")),
        ("orange", _("Orange")),
        ("red", _("Rot")),
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
    weather_design = models.CharField(
        max_length=20,
        choices=WEATHER_DESIGN_CHOICES,
        default=WEATHER_DESIGN_CLEAN,
    )
    weather_style = models.CharField(
        max_length=20,
        choices=WEATHER_STYLE_CHOICES,
        default=WEATHER_STYLE_CLASSIC,
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


class DrawingGameLobby(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_PLAYING = "playing"
    STATUS_FINISHED = "finished"

    STATUS_CHOICES = [
        (STATUS_WAITING, _("Wartet")),
        (STATUS_PLAYING, _("Läuft")),
        (STATUS_FINISHED, _("Beendet")),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_drawing_lobbies",
    )
    name = models.CharField(max_length=80, default="Zeichen-Lobby")
    code = models.SlugField(max_length=16, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)

    rounds_count = models.PositiveSmallIntegerField(default=3)
    draw_time_seconds = models.PositiveSmallIntegerField(default=80)
    max_players = models.PositiveSmallIntegerField(default=8)
    custom_words = models.TextField(blank=True)
    use_only_custom_words = models.BooleanField(default=False)

    current_round_number = models.PositiveSmallIntegerField(default=1)
    current_turn_index = models.PositiveIntegerField(default=0)
    current_word = models.CharField(max_length=80, blank=True)
    current_word_choices = models.JSONField(default=list, blank=True)
    current_drawing = models.JSONField(default=list, blank=True)
    round_started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Skribble-Lobby"
        verbose_name_plural = "Skribble-Lobbys"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["owner", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def is_waiting(self):
        return self.status == self.STATUS_WAITING

    @property
    def is_playing(self):
        return self.status == self.STATUS_PLAYING

    @property
    def is_finished(self):
        return self.status == self.STATUS_FINISHED

    @property
    def custom_word_list(self):
        return [word.strip() for word in self.custom_words.replace(";", ",").split(",") if word.strip()]


class DrawingGamePlayer(models.Model):
    AVATAR_BASE_CHOICES = [
        ("round", _("Rund")),
        ("square", _("Eckig")),
        ("robot", _("Roboter")),
        ("cat", _("Katze")),
        ("ghost", _("Geist")),
        ("ninja", _("Ninja")),
    ]

    lobby = models.ForeignKey(
        DrawingGameLobby,
        on_delete=models.CASCADE,
        related_name="players",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skribble_players",
    )
    display_name = models.CharField(max_length=40, blank=True)
    avatar_base = models.CharField(max_length=20, choices=AVATAR_BASE_CHOICES, default="round")
    avatar_color = models.CharField(max_length=20, default="#4f8cff")
    accent_color = models.CharField(max_length=20, default="#ffffff")
    score = models.PositiveIntegerField(default=0)
    is_ready = models.BooleanField(default=False)
    has_guessed_current_word = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["lobby", "user"], name="unique_drawing_player_per_lobby"),
        ]
        verbose_name = "Skribble-Spieler"
        verbose_name_plural = "Skribble-Spieler"

    def __str__(self):
        return f"{self.display_label} · {self.lobby.code}"

    @property
    def display_label(self):
        return self.display_name or self.user.get_full_name() or self.user.username


class DrawingGameInvite(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Offen")),
        (STATUS_ACCEPTED, _("Angenommen")),
        (STATUS_DECLINED, _("Abgelehnt")),
    ]

    lobby = models.ForeignKey(
        DrawingGameLobby,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_drawing_invites",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_drawing_invites",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["lobby", "to_user"], name="unique_drawing_invite_per_lobby_user"),
            models.CheckConstraint(condition=~models.Q(from_user=models.F("to_user")), name="drawing_invite_prevent_self"),
        ]
        verbose_name = "Skribble-Einladung"
        verbose_name_plural = "Skribble-Einladungen"

    def __str__(self):
        return f"{self.from_user} → {self.to_user} · {self.lobby.code}"


class DrawingGameGuess(models.Model):
    lobby = models.ForeignKey(
        DrawingGameLobby,
        on_delete=models.CASCADE,
        related_name="guesses",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skribble_guesses",
    )
    round_number = models.PositiveSmallIntegerField(default=1)
    turn_index = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=160)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["lobby", "round_number", "turn_index", "created_at"]),
        ]
        verbose_name = "Skribble-Rateversuch"
        verbose_name_plural = "Skribble-Rateversuche"

    def __str__(self):
        return f"{self.user}: {self.message[:30]}"
