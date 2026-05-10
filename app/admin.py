from django.contrib import admin

from .models import AvatarCharacter, Shortcut, ShortcutSection


@admin.register(AvatarCharacter)
class AvatarCharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "nation", "order", "created_at")
    list_filter = ("nation",)
    search_fields = ("name", "description")
    ordering = ("order", "created_at")


admin.site.register(Shortcut)
admin.site.register(ShortcutSection)
