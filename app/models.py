from django.conf import settings
from django.db import models
from django.core.validators import FileExtensionValidator
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
    STATUS_ONLINE = "online"
    STATUS_BUSY = "busy"
    STATUS_AWAY = "away"
    STATUS_DND = "dnd"
    STATUS_INVISIBLE = "invisible"

    STATUS_CHOICES = [
        (STATUS_ONLINE, _("Online")),
        (STATUS_BUSY, _("Beschäftigt")),
        (STATUS_AWAY, _("Abwesend")),
        (STATUS_DND, _("Nicht stören")),
        (STATUS_INVISIBLE, _("Unsichtbar")),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ONLINE)
    status_text = models.CharField(max_length=80, blank=True)
    privacy_show_online = models.BooleanField(default=True)
    privacy_show_friends = models.BooleanField(default=True)
    privacy_show_highscores = models.BooleanField(default=True)
    privacy_show_chat_button = models.BooleanField(default=True)
    notify_chat = models.BooleanField(default=True)
    notify_friend_requests = models.BooleanField(default=True)
    notify_skribble = models.BooleanField(default=True)
    browser_notifications = models.BooleanField(default=False)
    sound_notifications = models.BooleanField(default=True)
    dnd_silence_notifications = models.BooleanField(default=True)
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


class UserPresence(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="presence",
    )
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Online-Status"
        verbose_name_plural = "Online-Status"
        indexes = [
            models.Index(fields=["last_seen"]),
        ]

    def __str__(self):
        return f"{self.user} · {self.last_seen}"

    @property
    def is_online(self):
        from django.utils import timezone
        return self.last_seen >= timezone.now() - timezone.timedelta(minutes=3)


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


class ChatRoom(models.Model):
    ROOM_DIRECT = "direct"
    ROOM_GROUP = "group"

    ROOM_CHOICES = [
        (ROOM_DIRECT, _("Direktchat")),
        (ROOM_GROUP, _("Gruppe")),
    ]

    room_type = models.CharField(max_length=20, choices=ROOM_CHOICES, default=ROOM_DIRECT)
    name = models.CharField(max_length=80, blank=True)
    description = models.CharField(max_length=220, blank=True)
    avatar = models.ImageField(upload_to="chat_group_avatars/", null=True, blank=True)
    direct_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_chat_rooms",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ChatRoomMember",
        related_name="chat_rooms",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["room_type", "updated_at"]),
            models.Index(fields=["direct_key"]),
        ]
        verbose_name = "Chatraum"
        verbose_name_plural = "Chaträume"

    def __str__(self):
        return self.name or f"Chat #{self.pk}"

    @classmethod
    def direct_key_for_users(cls, user_a, user_b):
        first_id, second_id = sorted([user_a.id, user_b.id])
        return f"direct:{first_id}:{second_id}"

    def title_for(self, user):
        if self.room_type == self.ROOM_GROUP:
            return self.name or _("Gruppe")

        other_member = (
            self.members
            .exclude(id=user.id)
            .first()
        )

        if other_member:
            return other_member.get_full_name() or other_member.username

        return _("Direktchat")


class ChatRoomMember(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="room_memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_memberships")
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    is_admin = models.BooleanField(default=False)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["room", "user"], name="unique_chat_room_member"),
        ]
        indexes = [
            models.Index(fields=["user", "room"]),
        ]
        verbose_name = "Chatmitglied"
        verbose_name_plural = "Chatmitglieder"

    def __str__(self):
        return f"{self.user} · {self.room}"


class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_chat_messages")
    text = models.TextField(max_length=1200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
        ]
        verbose_name = "Chatnachricht"
        verbose_name_plural = "Chatnachrichten"

    def __str__(self):
        return f"{self.sender}: {self.text[:40]}"


def chat_attachment_upload_path(instance, filename):
    return f"chat_attachments/room_{instance.message.room_id}/{instance.message_id}_{filename}"


def validate_chat_attachment_size(file):
    from django.core.exceptions import ValidationError
    max_size = 8 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError(_("Anhänge dürfen maximal 8 MB groß sein."))


class ChatAttachment(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(
        upload_to=chat_attachment_upload_path,
        validators=[validate_chat_attachment_size],
    )
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Chat-Anhang"
        verbose_name_plural = "Chat-Anhänge"

    def __str__(self):
        return self.original_name

    @property
    def is_image(self):
        return self.content_type.startswith("image/")

    @property
    def filename(self):
        return self.original_name or self.file.name.rsplit("/", 1)[-1]


class ChatMessageReaction(models.Model):
    EMOJI_CHOICES = [
        ("👍", "👍"),
        ("❤️", "❤️"),
        ("😂", "😂"),
        ("😮", "😮"),
        ("😢", "😢"),
        ("🙏", "🙏"),
    ]

    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_reactions")
    emoji = models.CharField(max_length=8, choices=EMOJI_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["message", "user"], name="unique_chat_message_reaction"),
        ]
        indexes = [
            models.Index(fields=["message", "emoji"]),
            models.Index(fields=["user", "updated_at"]),
        ]
        verbose_name = "Chatreaktion"
        verbose_name_plural = "Chatreaktionen"

    def __str__(self):
        return f"{self.user} {self.emoji} → {self.message_id}"


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
    WIDGET_CHAT = "chat"
    WIDGET_FRIENDS = "friends"
    WIDGET_SKRIBBLE = "skribble"
    WIDGET_TICTACTOE = "tictactoe"
    WIDGET_STADTLANDFLUSS = "stadtlandfluss"

    WIDGET_CHOICES = [
        (WIDGET_WEATHER, _("Wetter")),
        (WIDGET_NOTES, _("Notizen")),
        (WIDGET_BENCHMARK, _("Human Benchmark")),
        (WIDGET_STATS, _("Schnellstatistiken")),
        (WIDGET_CLOCK, _("Uhr")),
        (WIDGET_CHAT, _("Chats")),
        (WIDGET_FRIENDS, _("Freunde")),
        (WIDGET_SKRIBBLE, _("Skribble")),
        (WIDGET_TICTACTOE, _("Tic Tac Toe")),
        (WIDGET_STADTLANDFLUSS, _("Stadt Land Fluss")),
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


class TicTacToeGame(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_PLAYING = "playing"
    STATUS_FINISHED = "finished"

    STATUS_CHOICES = [
        (STATUS_WAITING, _("Wartet")),
        (STATUS_PLAYING, _("Läuft")),
        (STATUS_FINISHED, _("Beendet")),
    ]

    SYMBOL_X = "X"
    SYMBOL_O = "O"

    SYMBOL_CHOICES = [
        (SYMBOL_X, "X"),
        (SYMBOL_O, "O"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_tictactoe_games",
    )
    player_x = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tictactoe_games_as_x",
        null=True,
        blank=True,
    )
    player_o = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tictactoe_games_as_o",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=80, default="Tic Tac Toe")
    code = models.SlugField(max_length=16, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    board = models.JSONField(default=list, blank=True)
    current_symbol = models.CharField(max_length=1, choices=SYMBOL_CHOICES, default=SYMBOL_X)
    winner_symbol = models.CharField(max_length=1, choices=SYMBOL_CHOICES, blank=True)
    winning_line = models.JSONField(default=list, blank=True)
    round_number = models.PositiveIntegerField(default=1)
    last_move_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Tic Tac Toe Spiel"
        verbose_name_plural = "Tic Tac Toe Spiele"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["player_x", "status"]),
            models.Index(fields=["player_o", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def normalized_board(self):
        board = self.board if isinstance(self.board, list) else []
        board = [cell if cell in {self.SYMBOL_X, self.SYMBOL_O} else "" for cell in board[:9]]
        return board + [""] * (9 - len(board))

    def symbol_for_user(self, user):
        if self.player_x_id == user.id:
            return self.SYMBOL_X
        if self.player_o_id == user.id:
            return self.SYMBOL_O
        return ""

    def opponent_for_user(self, user):
        if self.player_x_id == user.id:
            return self.player_o
        if self.player_o_id == user.id:
            return self.player_x
        return None


class TicTacToeInvite(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Offen")),
        (STATUS_ACCEPTED, _("Angenommen")),
        (STATUS_DECLINED, _("Abgelehnt")),
    ]

    game = models.ForeignKey(
        TicTacToeGame,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_tictactoe_invites",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_tictactoe_invites",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["game", "to_user"], name="unique_tictactoe_invite_per_game_user"),
            models.CheckConstraint(condition=~models.Q(from_user=models.F("to_user")), name="tictactoe_invite_prevent_self"),
        ]
        indexes = [
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["game", "status"]),
        ]
        verbose_name = "Tic Tac Toe Einladung"
        verbose_name_plural = "Tic Tac Toe Einladungen"

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} · {self.game}"


class ConnectFourGame(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_PLAYING = "playing"
    STATUS_FINISHED = "finished"

    STATUS_CHOICES = [
        (STATUS_WAITING, _("Wartet")),
        (STATUS_PLAYING, _("Läuft")),
        (STATUS_FINISHED, _("Beendet")),
    ]

    DISC_RED = "R"
    DISC_YELLOW = "Y"

    DISC_CHOICES = [
        (DISC_RED, _("Rot")),
        (DISC_YELLOW, _("Gelb")),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_connectfour_games",
    )
    player_red = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="connectfour_games_as_red",
        null=True,
        blank=True,
    )
    player_yellow = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="connectfour_games_as_yellow",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=80, default="Vier gewinnt")
    code = models.SlugField(max_length=16, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    board = models.JSONField(default=list, blank=True)
    current_disc = models.CharField(max_length=1, choices=DISC_CHOICES, default=DISC_RED)
    winner_disc = models.CharField(max_length=1, choices=DISC_CHOICES, blank=True)
    winning_line = models.JSONField(default=list, blank=True)
    last_move = models.JSONField(default=dict, blank=True)
    round_number = models.PositiveIntegerField(default=1)
    last_move_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Vier gewinnt Spiel"
        verbose_name_plural = "Vier gewinnt Spiele"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["player_red", "status"]),
            models.Index(fields=["player_yellow", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def normalized_board(self):
        board = self.board if isinstance(self.board, list) else []
        board = [cell if cell in {self.DISC_RED, self.DISC_YELLOW} else "" for cell in board[:42]]
        return board + [""] * (42 - len(board))

    def disc_for_user(self, user):
        if self.player_red_id == user.id:
            return self.DISC_RED
        if self.player_yellow_id == user.id:
            return self.DISC_YELLOW
        return ""

    def opponent_for_user(self, user):
        if self.player_red_id == user.id:
            return self.player_yellow
        if self.player_yellow_id == user.id:
            return self.player_red
        return None


class ConnectFourInvite(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Offen")),
        (STATUS_ACCEPTED, _("Angenommen")),
        (STATUS_DECLINED, _("Abgelehnt")),
    ]

    game = models.ForeignKey(
        ConnectFourGame,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_connectfour_invites",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_connectfour_invites",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["game", "to_user"], name="unique_connectfour_invite_per_game_user"),
            models.CheckConstraint(condition=~models.Q(from_user=models.F("to_user")), name="connectfour_invite_prevent_self"),
        ]
        indexes = [
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["game", "status"]),
        ]
        verbose_name = "Vier gewinnt Einladung"
        verbose_name_plural = "Vier gewinnt Einladungen"

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} - {self.game}"


class BattleshipGame(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_SETUP = "setup"
    STATUS_PLAYING = "playing"
    STATUS_FINISHED = "finished"

    STATUS_CHOICES = [
        (STATUS_WAITING, _("Wartet")),
        (STATUS_SETUP, _("Flottenaufbau")),
        (STATUS_PLAYING, _("Läuft")),
        (STATUS_FINISHED, _("Beendet")),
    ]

    SIDE_A = "A"
    SIDE_B = "B"

    SIDE_CHOICES = [
        (SIDE_A, "A"),
        (SIDE_B, "B"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_battleship_games",
    )
    player_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="battleship_games_as_a",
        null=True,
        blank=True,
    )
    player_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="battleship_games_as_b",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=80, default="Schiffe versenken")
    code = models.SlugField(max_length=16, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    fleet_a = models.JSONField(default=list, blank=True)
    fleet_b = models.JSONField(default=list, blank=True)
    shots_a = models.JSONField(default=list, blank=True)
    shots_b = models.JSONField(default=list, blank=True)
    ready_a = models.BooleanField(default=False)
    ready_b = models.BooleanField(default=False)
    current_turn = models.CharField(max_length=1, choices=SIDE_CHOICES, default=SIDE_A)
    winner_side = models.CharField(max_length=1, choices=SIDE_CHOICES, blank=True)
    round_number = models.PositiveIntegerField(default=1)
    last_move_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Schiffe versenken Spiel"
        verbose_name_plural = "Schiffe versenken Spiele"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["player_a", "status"]),
            models.Index(fields=["player_b", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def side_for_user(self, user):
        if self.player_a_id == user.id:
            return self.SIDE_A
        if self.player_b_id == user.id:
            return self.SIDE_B
        return ""

    def opponent_for_user(self, user):
        if self.player_a_id == user.id:
            return self.player_b
        if self.player_b_id == user.id:
            return self.player_a
        return None

    @property
    def is_full(self):
        return bool(self.player_a_id and self.player_b_id)


class BattleshipInvite(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Offen")),
        (STATUS_ACCEPTED, _("Angenommen")),
        (STATUS_DECLINED, _("Abgelehnt")),
    ]

    game = models.ForeignKey(
        BattleshipGame,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_battleship_invites",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_battleship_invites",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["game", "to_user"], name="unique_battleship_invite_per_game_user"),
            models.CheckConstraint(condition=~models.Q(from_user=models.F("to_user")), name="battleship_invite_prevent_self"),
        ]
        indexes = [
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["game", "status"]),
        ]
        verbose_name = "Schiffe versenken Einladung"
        verbose_name_plural = "Schiffe versenken Einladungen"

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} · {self.game}"


class StadtLandFlussLobby(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_PLAYING = "playing"
    STATUS_ROUND_SUMMARY = "round_summary"
    STATUS_FINISHED = "finished"

    STATUS_CHOICES = [
        (STATUS_WAITING, _("Wartet")),
        (STATUS_PLAYING, _("Läuft")),
        (STATUS_ROUND_SUMMARY, _("Rundenauswertung")),
        (STATUS_FINISHED, _("Beendet")),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_stadtlandfluss_lobbies",
    )
    name = models.CharField(max_length=80, default="Stadt Land Fluss")
    code = models.SlugField(max_length=16, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    categories = models.JSONField(default=list, blank=True)
    rounds_count = models.PositiveSmallIntegerField(default=5)
    round_time_seconds = models.PositiveSmallIntegerField(default=90)
    max_players = models.PositiveSmallIntegerField(default=8)
    current_round_number = models.PositiveSmallIntegerField(default=0)
    current_letter = models.CharField(max_length=1, blank=True)
    used_letters = models.JSONField(default=list, blank=True)
    round_started_at = models.DateTimeField(null=True, blank=True)
    round_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Stadt Land Fluss Lobby"
        verbose_name_plural = "Stadt Land Fluss Lobbys"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["owner", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def normalized_categories(self):
        categories = self.categories if isinstance(self.categories, list) else []
        cleaned = [str(category).strip()[:40] for category in categories if str(category).strip()]
        return cleaned or ["Stadt", "Land", "Fluss", "Name", "Tier", "Beruf"]


class StadtLandFlussPlayer(models.Model):
    lobby = models.ForeignKey(
        StadtLandFlussLobby,
        on_delete=models.CASCADE,
        related_name="players",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stadtlandfluss_players",
    )
    display_name = models.CharField(max_length=40, blank=True)
    score = models.PositiveIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["lobby", "user"], name="unique_stadtlandfluss_player_per_lobby"),
        ]
        verbose_name = "Stadt Land Fluss Spieler"
        verbose_name_plural = "Stadt Land Fluss Spieler"

    def __str__(self):
        return f"{self.display_label} - {self.lobby.code}"

    @property
    def display_label(self):
        return self.display_name or self.user.get_full_name() or self.user.username


class StadtLandFlussRoundAnswer(models.Model):
    lobby = models.ForeignKey(
        StadtLandFlussLobby,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    player = models.ForeignKey(
        StadtLandFlussPlayer,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    round_number = models.PositiveSmallIntegerField(default=1)
    letter = models.CharField(max_length=1)
    answers = models.JSONField(default=dict, blank=True)
    points = models.JSONField(default=dict, blank=True)
    total_points = models.PositiveSmallIntegerField(default=0)
    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["round_number", "player__joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lobby", "player", "round_number"],
                name="unique_stadtlandfluss_answer_per_round_player",
            ),
        ]
        indexes = [
            models.Index(fields=["lobby", "round_number"]),
        ]
        verbose_name = "Stadt Land Fluss Antwort"
        verbose_name_plural = "Stadt Land Fluss Antworten"

    def __str__(self):
        return f"{self.player.display_label} - Runde {self.round_number}"


class StadtLandFlussInvite(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Offen")),
        (STATUS_ACCEPTED, _("Angenommen")),
        (STATUS_DECLINED, _("Abgelehnt")),
    ]

    lobby = models.ForeignKey(
        StadtLandFlussLobby,
        on_delete=models.CASCADE,
        related_name="invites",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_stadtlandfluss_invites",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_stadtlandfluss_invites",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["lobby", "to_user"], name="unique_stadtlandfluss_invite_per_lobby_user"),
            models.CheckConstraint(condition=~models.Q(from_user=models.F("to_user")), name="stadtlandfluss_invite_prevent_self"),
        ]
        indexes = [
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["lobby", "status"]),
        ]
        verbose_name = "Stadt Land Fluss Einladung"
        verbose_name_plural = "Stadt Land Fluss Einladungen"

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} - {self.lobby}"


class DrawingGameLobby(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_PLAYING = "playing"
    STATUS_ROUND_SUMMARY = "round_summary"
    STATUS_FINISHED = "finished"

    STATUS_CHOICES = [
        (STATUS_WAITING, _("Wartet")),
        (STATUS_PLAYING, _("Läuft")),
        (STATUS_ROUND_SUMMARY, _("Rundenübersicht")),
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
    round_summary = models.JSONField(default=dict, blank=True)
    summary_started_at = models.DateTimeField(null=True, blank=True)

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
    def is_round_summary(self):
        return self.status == self.STATUS_ROUND_SUMMARY

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
    points_awarded = models.PositiveSmallIntegerField(default=0)
    drawer_points_awarded = models.PositiveSmallIntegerField(default=0)
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


class ChatMessageRead(models.Model):
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name="read_receipts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_read_receipts")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["read_at"]
        constraints = [models.UniqueConstraint(fields=["message", "user"], name="unique_chat_message_read_user")]
        indexes = [models.Index(fields=["message", "user"]), models.Index(fields=["user", "read_at"])]
        verbose_name = "Gelesene Chatnachricht"
        verbose_name_plural = "Gelesene Chatnachrichten"

    def __str__(self):
        return f"{self.user} gelesen {self.message_id}"


def profile_gallery_upload_path(instance, filename):
    return f"profile_gallery/user_{instance.user_id}/{filename}"


class ProfileGalleryImage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to=profile_gallery_upload_path)
    caption = models.CharField(max_length=120, blank=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
        verbose_name = "Profil-Galeriebild"
        verbose_name_plural = "Profil-Galeriebilder"

    def __str__(self):
        return self.caption or f"Galeriebild {self.pk}"


class UserBlock(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_users")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_by_users")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_user_block"),
            models.CheckConstraint(condition=~models.Q(blocker=models.F("blocked")), name="prevent_self_block"),
        ]
        indexes = [models.Index(fields=["blocker", "blocked"])]
        verbose_name = "Blockierter Nutzer"
        verbose_name_plural = "Blockierte Nutzer"

    def __str__(self):
        return f"{self.blocker} blockiert {self.blocked}"


class UserReport(models.Model):
    REASON_SPAM = "spam"
    REASON_HARASSMENT = "harassment"
    REASON_CONTENT = "content"
    REASON_OTHER = "other"
    REASON_CHOICES = [
        (REASON_SPAM, _("Spam")),
        (REASON_HARASSMENT, _("Belästigung")),
        (REASON_CONTENT, _("Unpassende Inhalte")),
        (REASON_OTHER, _("Sonstiges")),
    ]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_user_reports")
    reported = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_user_reports")
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default=REASON_OTHER)
    message = models.TextField(max_length=1000, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["reported", "is_resolved", "-created_at"])]
        verbose_name = "Nutzermeldung"
        verbose_name_plural = "Nutzermeldungen"

    def __str__(self):
        return f"Meldung: {self.reporter} → {self.reported}"


class SkribbleStats(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skribble_stats")
    games_played = models.PositiveIntegerField(default=0)
    games_won = models.PositiveIntegerField(default=0)
    correct_guesses = models.PositiveIntegerField(default=0)
    drawings_made = models.PositiveIntegerField(default=0)
    total_score = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Skribble-Statistik"
        verbose_name_plural = "Skribble-Statistiken"

    def __str__(self):
        return f"Skribble Stats: {self.user}"

    @property
    def win_rate(self):
        if not self.games_played:
            return 0
        return round((self.games_won / self.games_played) * 100)


class ToolFavorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tool_favorites")
    tool_key = models.CharField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "tool_key"], name="unique_tool_favorite_per_user")]
        indexes = [models.Index(fields=["user", "tool_key"])]
        verbose_name = "Tool-Favorit"
        verbose_name_plural = "Tool-Favoriten"

    def __str__(self):
        return f"{self.user} · {self.tool_key}"


class InboxItem(models.Model):
    TYPE_SYSTEM = "system"
    TYPE_CHAT = "chat"
    TYPE_FRIEND = "friend"
    TYPE_SKRIBBLE = "skribble"
    TYPE_FEEDBACK = "feedback"

    TYPE_CHOICES = [
        (TYPE_SYSTEM, _("System")),
        (TYPE_CHAT, _("Chat")),
        (TYPE_FRIEND, _("Freunde")),
        (TYPE_SKRIBBLE, _("Skribble")),
        (TYPE_FEEDBACK, _("Feedback")),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inbox_items")
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    title = models.CharField(max_length=120)
    message = models.TextField(blank=True)
    target_url = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=80, default="fa-solid fa-bell")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "-created_at"])]
        verbose_name = "Inbox-Eintrag"
        verbose_name_plural = "Inbox-Einträge"

    def __str__(self):
        return self.title


class ToolFeedback(models.Model):
    TYPE_FEEDBACK = "feedback"
    TYPE_BUG = "bug"
    TYPE_IDEA = "idea"

    TYPE_CHOICES = [
        (TYPE_FEEDBACK, _("Feedback")),
        (TYPE_BUG, _("Bug")),
        (TYPE_IDEA, _("Feature-Idee")),
    ]

    STATUS_OPEN = "open"
    STATUS_PLANNED = "planned"
    STATUS_DONE = "done"

    STATUS_CHOICES = [
        (STATUS_OPEN, _("Offen")),
        (STATUS_PLANNED, _("Geplant")),
        (STATUS_DONE, _("Erledigt")),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="tool_feedback")
    tool_key = models.CharField(max_length=60, blank=True)
    feedback_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_FEEDBACK)
    title = models.CharField(max_length=120)
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tool_key", "status", "-created_at"])]
        verbose_name = "Tool-Feedback"
        verbose_name_plural = "Tool-Feedback"

    def __str__(self):
        return self.title
