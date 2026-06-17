from django.contrib import admin, messages
from django.contrib.admin.sites import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import (
    AvatarCharacter,
    BudgetCategory,
    BudgetEntry,
    BudgetMonth,
    ChatAttachment,
    ChatMessage,
    ChatMessageReaction,
    ChatTypingStatus,
    ChatRoom,
    ChatRoomMember,
    ClockSettings,
    ClockTimerPreset,
    ClockWorldCity,
    ConnectFourGame,
    ConnectFourInvite,
    CookieClickerHighScore,
    CookieCosmosV2Save,
    Game2048HighScore,
    DrawingGameGuess as SkribbleGuess,
    DrawingGameInvite as SkribbleInvite,
    DrawingGameLobby as SkribbleLobby,
    DrawingGamePlayer as SkribblePlayer,
    FeatureComment,
    FeatureIdea,
    FeatureVote,
    FileShare,
    Friendship,
    HumanBenchmarkHighScore,
    HumanBenchmarkScore,
    HangmanInvite,
    HangmanLobby,
    HangmanPlayer,
    InboxItem,
    ModerationAuditLog,
    Note,
    PongGame,
    PongInvite,
    SecurityEvent,
    Shortcut,
    ShortcutSection,
    SiteAccessSettings,
    StadtLandFlussInvite,
    StadtLandFlussLobby,
    StadtLandFlussPlayer,
    StadtLandFlussRoundAnswer,
    ToolFavorite,
    ToolFeedback,
    UserProfile,
    UserSuspension,
    UserTwoFactorSettings,
    WeatherLocation,
)




@admin.register(BudgetCategory)
class BudgetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "user", "is_default", "created_at")
    list_filter = ("kind", "is_default", "created_at")
    search_fields = ("name", "user__username", "user__email")
    readonly_fields = ("created_at",)


@admin.register(BudgetMonth)
class BudgetMonthAdmin(admin.ModelAdmin):
    list_display = ("user", "month", "year", "planned_income", "expense_limit", "savings_goal", "updated_at")
    list_filter = ("year", "month", "updated_at")
    search_fields = ("user__username", "user__email", "notes")
    readonly_fields = ("created_at", "updated_at")


@admin.register(BudgetEntry)
class BudgetEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "entry_type", "amount", "category", "date", "is_fixed", "recurrence")
    list_filter = ("entry_type", "is_fixed", "recurrence", "date", "category")
    search_fields = ("title", "note", "user__username", "user__email", "category__name")
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")




@admin.register(CookieCosmosV2Save)
class CookieCosmosV2SaveAdmin(admin.ModelAdmin):
    list_display = ("user", "prestige_level", "lifetime_cookies", "cps", "buildings_count", "updated_at")
    list_filter = ("prestige_level", "updated_at", "last_manual_save")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at", "last_manual_save")

@admin.register(SiteAccessSettings)
class SiteAccessSettingsAdmin(admin.ModelAdmin):
    list_display = ("login_registration_locked", "updated_by", "updated_at")
    readonly_fields = ("updated_at",)



class UserTwoFactorSettingsInline(admin.StackedInline):
    model = UserTwoFactorSettings
    can_delete = True
    extra = 0
    max_num = 1
    fields = ("is_enabled", "confirmed_at", "updated_at", "secret_key")
    readonly_fields = ("confirmed_at", "updated_at", "secret_key")
    verbose_name = _("Zwei-Faktor-Authentifizierung")
    verbose_name_plural = _("Zwei-Faktor-Authentifizierung")

    def has_add_permission(self, request, obj=None):
        return False


UserModel = get_user_model()


try:
    admin.site.unregister(UserModel)
except NotRegistered:
    pass


@admin.register(UserModel)
class UserAdmin(DjangoUserAdmin):
    inlines = tuple(getattr(DjangoUserAdmin, "inlines", ())) + (UserTwoFactorSettingsInline,)
    list_display = tuple(getattr(DjangoUserAdmin, "list_display", ())) + ("two_factor_status",)
    actions = list(getattr(DjangoUserAdmin, "actions", []) or []) + ["reset_two_factor_for_users"]

    @admin.display(boolean=True, description=_("2FA aktiv"))
    def two_factor_status(self, obj):
        return bool(UserTwoFactorSettings.enabled_for_user(obj))

    @admin.action(description=_("2FA für ausgewählte Nutzer zurücksetzen"))
    def reset_two_factor_for_users(self, request, queryset):
        deleted_count, _deleted_per_model = UserTwoFactorSettings.objects.filter(user__in=queryset).delete()
        self.message_user(
            request,
            _("2FA wurde für %(count)s Nutzer zurückgesetzt.") % {"count": deleted_count},
            messages.SUCCESS,
        )


@admin.register(UserTwoFactorSettings)
class UserTwoFactorSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "is_enabled", "confirmed_at", "updated_at")
    list_filter = ("is_enabled", "confirmed_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("updated_at", "confirmed_at")
    actions = ("reset_selected_two_factor_settings",)

    @admin.action(description=_("Ausgewählte 2FA-Einstellungen löschen/zurücksetzen"))
    def reset_selected_two_factor_settings(self, request, queryset):
        deleted_count, _deleted_per_model = queryset.delete()
        self.message_user(
            request,
            _("%(count)s 2FA-Einstellung wurde zurückgesetzt.") % {"count": deleted_count},
            messages.SUCCESS,
        )



class FeatureCommentInline(admin.TabularInline):
    model = FeatureComment
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("user", "text", "created_at")


class FeatureVoteInline(admin.TabularInline):
    model = FeatureVote
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("user", "created_at")


@admin.register(FeatureIdea)
class FeatureIdeaAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "priority", "status", "vote_count", "created_at")
    list_filter = ("status", "category", "priority", "created_at")
    search_fields = ("title", "description", "admin_note", "author__username", "author__email")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    inlines = (FeatureVoteInline, FeatureCommentInline)

    @admin.display(description=_("Votes"))
    def vote_count(self, obj):
        return obj.votes.count()


@admin.register(FeatureVote)
class FeatureVoteAdmin(admin.ModelAdmin):
    list_display = ("idea", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("idea__title", "user__username", "user__email")
    readonly_fields = ("created_at",)


@admin.register(FeatureComment)
class FeatureCommentAdmin(admin.ModelAdmin):
    list_display = ("idea", "user", "short_text", "created_at")
    list_filter = ("created_at",)
    search_fields = ("idea__title", "user__username", "user__email", "text")
    readonly_fields = ("created_at",)

    def short_text(self, obj):
        return obj.text[:70]


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "event_type", "severity", "ip_address", "short_user_agent")
    list_filter = ("event_type", "severity", "created_at")
    search_fields = ("user__username", "user__email", "ip_address", "user_agent", "note")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


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


@admin.register(ChatTypingStatus)
class ChatTypingStatusAdmin(admin.ModelAdmin):
    list_display = ("room", "user", "is_typing", "updated_at")
    list_filter = ("is_typing", "updated_at")
    search_fields = ("room__name", "user__username", "user__email")
    readonly_fields = ("updated_at",)


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
    list_display = ("user", "file_share_limit", "updated_at", "created_at")
    list_filter = ("file_share_limit",)
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("from_user__username", "from_user__email", "to_user__username", "to_user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Game2048HighScore)
class Game2048HighScoreAdmin(admin.ModelAdmin):
    list_display = ("user", "score", "best_tile", "moves", "won", "games_played", "achieved_at")
    list_filter = ("won", "best_tile", "achieved_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("achieved_at",)


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


@admin.register(CookieClickerHighScore)
class CookieClickerHighScoreAdmin(admin.ModelAdmin):
    list_display = ("user", "display_score", "cps", "stardust", "ascensions", "achieved_at")
    list_filter = ("stardust", "ascensions")
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


@admin.register(ConnectFourGame)
class ConnectFourGameAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "owner", "status", "player_red", "player_yellow", "round_number", "updated_at")
    list_filter = ("status", "owner", "created_at")
    search_fields = ("name", "code", "owner__username", "player_red__username", "player_yellow__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ConnectFourInvite)
class ConnectFourInviteAdmin(admin.ModelAdmin):
    list_display = ("game", "from_user", "to_user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("game__code", "from_user__username", "to_user__username")


@admin.register(PongGame)
class PongGameAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "owner", "status", "player_left", "player_right", "score_left", "score_right", "target_score", "round_number", "updated_at")
    list_filter = ("status", "owner", "created_at")
    search_fields = ("name", "code", "owner__username", "player_left__username", "player_right__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PongInvite)
class PongInviteAdmin(admin.ModelAdmin):
    list_display = ("game", "from_user", "to_user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("game__code", "from_user__username", "to_user__username")


@admin.register(StadtLandFlussLobby)
class StadtLandFlussLobbyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "owner", "status", "rounds_count", "round_time_seconds", "max_players", "updated_at")
    list_filter = ("status", "owner", "created_at")
    search_fields = ("name", "code", "owner__username", "owner__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StadtLandFlussPlayer)
class StadtLandFlussPlayerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "lobby", "score", "joined_at")
    search_fields = ("display_name", "user__username", "lobby__code")


@admin.register(StadtLandFlussRoundAnswer)
class StadtLandFlussRoundAnswerAdmin(admin.ModelAdmin):
    list_display = ("lobby", "player", "round_number", "letter", "total_points", "is_submitted")
    list_filter = ("is_submitted", "letter")
    search_fields = ("lobby__code", "player__user__username")


@admin.register(StadtLandFlussInvite)
class StadtLandFlussInviteAdmin(admin.ModelAdmin):
    list_display = ("lobby", "from_user", "to_user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("lobby__code", "from_user__username", "to_user__username")




@admin.register(HangmanLobby)
class HangmanLobbyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "owner", "status", "round_number", "max_mistakes", "updated_at")
    list_filter = ("status", "owner", "created_at")
    search_fields = ("name", "code", "owner__username", "owner__email", "word")
    readonly_fields = ("created_at", "updated_at")


@admin.register(HangmanPlayer)
class HangmanPlayerAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "lobby", "score", "joined_at", "last_seen")
    search_fields = ("display_name", "user__username", "lobby__code")


@admin.register(HangmanInvite)
class HangmanInviteAdmin(admin.ModelAdmin):
    list_display = ("lobby", "from_user", "to_user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("lobby__code", "from_user__username", "to_user__username")

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


@admin.register(UserSuspension)
class UserSuspensionAdmin(admin.ModelAdmin):
    list_display = ("user", "moderator", "is_active", "starts_at", "ends_at", "lifted_at")
    list_filter = ("is_active", "starts_at", "ends_at")
    search_fields = ("user__username", "moderator__username", "reason")
    readonly_fields = ("created_at", "lifted_at")


@admin.register(ModerationAuditLog)
class ModerationAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_user", "summary", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("summary", "actor__username", "target_user__username")
    readonly_fields = ("created_at",)


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


@admin.register(FileShare)
class FileShareAdmin(admin.ModelAdmin):
    list_display = ("original_name", "owner", "size", "is_public_link", "download_count", "created_at")
    list_filter = ("is_public_link", "content_type", "created_at")
    search_fields = ("original_name", "owner__username", "owner__email", "token")
    readonly_fields = ("token", "download_count", "last_downloaded_at", "created_at")
    filter_horizontal = ("recipients",)
