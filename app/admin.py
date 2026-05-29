from django.contrib import admin

from .models import (
    AvatarCharacter,
    ChatAttachment,
    ChatMessage,
    ChatMessageReaction,
    ChatRoom,
    ChatRoomMember,
    ClockSettings,
    ClockTimerPreset,
    ClockWorldCity,
    DrawingGameGuess as SkribbleGuess,
    DrawingGameInvite as SkribbleInvite,
    DrawingGameLobby as SkribbleLobby,
    DrawingGamePlayer as SkribblePlayer,
    Friendship,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    InboxItem,
    Note,
    Shortcut,
    ShortcutSection,
    ToolFavorite,
    ToolFeedback,
    UserProfile,
    WeatherLocation,
)




@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "room_type", "created_by", "updated_at", "created_at")
    list_filter = ("room_type", "created_at")
    search_fields = ("name", "created_by__username", "members__username")
    readonly_fields = ("created_at", "updated_at")

    def display_name(self, obj):
        return obj.name or str(obj)


@admin.register(ChatRoomMember)
class ChatRoomMemberAdmin(admin.ModelAdmin):
    list_display = ("room", "user", "is_admin", "joined_at", "last_read_at")
    list_filter = ("is_admin", "joined_at")
    search_fields = ("room__name", "user__username", "user__email")
    readonly_fields = ("joined_at",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("room", "sender", "short_text", "created_at")
    list_filter = ("created_at", "sender")
    search_fields = ("text", "sender__username", "room__name")
    readonly_fields = ("created_at", "edited_at")

    def short_text(self, obj):
        return obj.text[:60]




@admin.register(ChatMessageReaction)
class ChatMessageReactionAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "emoji", "created_at", "updated_at")
    list_filter = ("emoji", "created_at")
    search_fields = ("message__text", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")

@admin.register(AvatarCharacter)
class AvatarCharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "nation", "order", "created_at")
    list_filter = ("nation", "user")
    search_fields = ("name", "description", "user__username")
    ordering = ("order", "created_at")


@admin.register(Shortcut)
class ShortcutAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "section", "is_favorite", "order", "created_at")
    list_filter = ("user", "is_favorite")
    search_fields = ("name", "url", "user__username")


@admin.register(ShortcutSection)
class ShortcutSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "color", "order", "is_collapsed", "created_at")
    list_filter = ("user", "color", "is_collapsed")
    search_fields = ("name", "user__username")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "color", "is_pinned", "is_archived", "updated_at")
    list_filter = ("user", "color", "is_pinned", "is_archived")
    search_fields = ("title", "content", "tags", "user__username")


@admin.register(WeatherLocation)
class WeatherLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "order", "created_at")
    list_filter = ("user",)
    search_fields = ("name", "user__username")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at", "created_at")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("from_user__username", "from_user__email", "to_user__username", "to_user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(HumanBenchmarkScore)
class HumanBenchmarkScoreAdmin(admin.ModelAdmin):
    list_display = ("user", "game", "display_score", "score", "created_at")
    list_filter = ("game", "user")
    search_fields = ("user__username", "user__email", "display_score")
    readonly_fields = ("created_at",)


@admin.register(HumanBenchmarkHighScore)
class HumanBenchmarkHighScoreAdmin(admin.ModelAdmin):
    list_display = ("user", "game", "display_score", "score", "achieved_at")
    list_filter = ("game", "user")
    search_fields = ("user__username", "user__email", "display_score")
    readonly_fields = ("achieved_at",)

@admin.register(ClockWorldCity)
class ClockWorldCityAdmin(admin.ModelAdmin):
    list_display = ("label", "timezone", "user", "order", "created_at")
    list_filter = ("timezone", "user")
    search_fields = ("label", "timezone", "user__username")


@admin.register(ClockTimerPreset)
class ClockTimerPresetAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "hours", "minutes", "seconds", "order", "created_at")
    list_filter = ("user",)
    search_fields = ("name", "user__username")


@admin.register(ClockSettings)
class ClockSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "volume", "ringtone", "updated_at")
    list_filter = ("ringtone",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("updated_at",)



@admin.register(SkribbleLobby)
class SkribbleLobbyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "owner", "status", "rounds_count", "draw_time_seconds", "max_players", "updated_at")
    list_filter = ("status", "owner", "created_at")
    search_fields = ("name", "code", "owner__username", "owner__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SkribblePlayer)
class SkribblePlayerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "lobby", "score", "avatar_base", "joined_at")
    list_filter = ("avatar_base", "lobby")
    search_fields = ("display_name", "user__username", "lobby__code")


@admin.register(SkribbleInvite)
class SkribbleInviteAdmin(admin.ModelAdmin):
    list_display = ("lobby", "from_user", "to_user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("lobby__code", "from_user__username", "to_user__username")


@admin.register(SkribbleGuess)
class SkribbleGuessAdmin(admin.ModelAdmin):
    list_display = ("lobby", "user", "round_number", "turn_index", "is_correct", "created_at")
    list_filter = ("is_correct", "created_at")
    search_fields = ("message", "user__username", "lobby__code")


@admin.register(ChatAttachment)
class ChatAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "message", "content_type", "size", "created_at")
    search_fields = ("original_name", "message__text", "message__sender__username")
    readonly_fields = ("created_at",)


@admin.register(ToolFavorite)
class ToolFavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "tool_key", "created_at")
    list_filter = ("tool_key",)
    search_fields = ("user__username", "tool_key")


@admin.register(InboxItem)
class InboxItemAdmin(admin.ModelAdmin):
    list_display = ("user", "item_type", "title", "is_read", "created_at")
    list_filter = ("item_type", "is_read", "created_at")
    search_fields = ("user__username", "title", "message")


@admin.register(ToolFeedback)
class ToolFeedbackAdmin(admin.ModelAdmin):
    list_display = ("title", "tool_key", "feedback_type", "rating", "status", "user", "created_at")
    list_filter = ("feedback_type", "status", "tool_key")
    search_fields = ("title", "message", "user__username")

# Platform/social Erweiterungen
try:
    from .models import ChatMessageRead, ProfileGalleryImage, SkribbleStats, UserBlock, UserReport

    @admin.register(ChatMessageRead)
    class ChatMessageReadAdmin(admin.ModelAdmin):
        list_display = ("message", "user", "read_at")
        search_fields = ("user__username", "message__text")
        list_filter = ("read_at",)

    @admin.register(ProfileGalleryImage)
    class ProfileGalleryImageAdmin(admin.ModelAdmin):
        list_display = ("user", "caption", "is_public", "created_at")
        search_fields = ("user__username", "caption")
        list_filter = ("is_public", "created_at")

    @admin.register(UserBlock)
    class UserBlockAdmin(admin.ModelAdmin):
        list_display = ("blocker", "blocked", "created_at")
        search_fields = ("blocker__username", "blocked__username")
        list_filter = ("created_at",)

    @admin.register(UserReport)
    class UserReportAdmin(admin.ModelAdmin):
        list_display = ("reporter", "reported", "reason", "is_resolved", "created_at")
        search_fields = ("reporter__username", "reported__username", "message")
        list_filter = ("reason", "is_resolved", "created_at")

    @admin.register(SkribbleStats)
    class SkribbleStatsAdmin(admin.ModelAdmin):
        list_display = ("user", "games_played", "games_won", "correct_guesses", "drawings_made", "total_score", "updated_at")
        search_fields = ("user__username",)
except admin.sites.AlreadyRegistered:
    pass
