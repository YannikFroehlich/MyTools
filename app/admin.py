from django.contrib import admin

from .models import AvatarCharacter, Note, Shortcut, ShortcutSection, WeatherLocation


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
