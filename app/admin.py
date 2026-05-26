from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import AvatarCharacter, Shortcut, ShortcutSection, UserNotePermission


class UserNotePermissionInline(admin.StackedInline):
    model = UserNotePermission
    can_delete = False
    extra = 1
    max_num = 1
    verbose_name_plural = "Notiz-Rechte"


admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (UserNotePermissionInline,)


@admin.register(AvatarCharacter)
class AvatarCharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "nation", "order", "created_at")
    list_filter = ("nation",)
    search_fields = ("name", "description")
    ordering = ("order", "created_at")


admin.site.register(Shortcut)
admin.site.register(ShortcutSection)
