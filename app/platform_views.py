from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .access_control import user_can_access_key
from .models import ChatRoom, DrawingGameInvite, FeatureIdea, FileShare, Friendship, InboxItem, Note, ToolFavorite, ToolFeedback, UserProfile
from .platform_forms import ToolFeedbackForm
from .platform_utils import resolve_tools, tool_by_key


@login_required
def favorites_view(request):
    favorite_keys = set(ToolFavorite.objects.filter(user=request.user).values_list("tool_key", flat=True))
    tools = resolve_tools(request, favorite_keys, include_inaccessible=True)
    categories = []
    for category in dict.fromkeys([tool["category"] for tool in tools]):
        categories.append({"name": category, "tools": [tool for tool in tools if tool["category"] == category]})
    return render(request, "app/favorites.html", {"tools": tools, "categories": categories})


@login_required
@require_POST
def favorite_toggle_view(request, tool_key):
    tool = tool_by_key(tool_key)
    if not tool:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Unbekanntes Tool.")}, status=404)
        messages.error(request, _("Dieses Tool gibt es nicht."))
        return redirect("favorites")

    if not user_can_access_key(request.user, tool_key):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": _("Kein Zugriff auf dieses Tool.")}, status=403)
        messages.error(request, _("Du hast keinen Zugriff auf dieses Tool."))
        return redirect("favorites")

    favorite, created = ToolFavorite.objects.get_or_create(user=request.user, tool_key=tool_key)
    is_favorite = True
    if not created:
        favorite.delete()
        is_favorite = False

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "is_favorite": is_favorite})

    messages.success(request, _("Favoriten wurden aktualisiert."))
    return redirect(request.POST.get("next") or "favorites")


def _search_match(query, *values):
    haystack = " ".join(str(value or "").lower() for value in values)
    return query in haystack


def _result(kind, title, subtitle, url, icon, badge="", theme="default"):
    return {
        "kind": kind,
        "title": str(title),
        "subtitle": str(subtitle or ""),
        "url": url,
        "icon": icon,
        "badge": str(badge or ""),
        "theme": theme,
    }


@login_required
@require_GET
def global_search_api(request):
    query = request.GET.get("q", "").strip().lower()
    favorite_keys = set(ToolFavorite.objects.filter(user=request.user).values_list("tool_key", flat=True))
    results = []

    tools = resolve_tools(request, favorite_keys)
    for tool in tools:
        if not query or _search_match(query, tool["label"], tool["category"], tool["key"]):
            results.append(_result(
                _("Tool"),
                tool["label"],
                tool["category"],
                tool["url"],
                tool["icon"],
                _("Favorit") if tool.get("is_favorite") else "",
                tool["key"],
            ))

    if query:
        note_qs = (
            Note.objects
            .filter(Q(user=request.user) | Q(shared_with=request.user), is_archived=False)
            .filter(Q(title__icontains=query) | Q(content__icontains=query) | Q(tags__icontains=query))
            .distinct()
            .order_by("-updated_at")[:6]
        )
        for note in note_qs:
            results.append(_result(
                _("Notiz"),
                note.title or _("Unbenannte Notiz"),
                note.updated_at.strftime("%d.%m.%Y %H:%M"),
                reverse("note_detail", args=[note.pk]),
                "fa-regular fa-note-sticky",
                theme="note-result",
            ))

        share_qs = (
            FileShare.objects
            .filter(Q(owner=request.user) | Q(recipients=request.user))
            .filter(original_name__icontains=query)
            .distinct()
            .order_by("-created_at")[:6]
        )
        for share in share_qs:
            results.append(_result(
                _("Datei"),
                share.original_name,
                share.human_size,
                reverse("file_share_download", args=[share.token]),
                share.icon_class,
                _("Link") if share.is_public_link else "",
                "file-result",
            ))

        user_qs = (
            UserProfile.objects
            .select_related("user")
            .filter(user__is_active=True)
            .filter(Q(user__username__icontains=query) | Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) | Q(bio__icontains=query))
            .order_by("user__username")[:6]
        )
        for profile in user_qs:
            results.append(_result(
                _("Nutzer"),
                profile.user.get_full_name() or profile.user.username,
                f"@{profile.user.username}",
                reverse("public_profile", args=[profile.user_id]),
                "fa-solid fa-user",
                theme="user-result",
            ))

        idea_qs = (
            FeatureIdea.objects
            .filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(admin_note__icontains=query))
            .order_by("-updated_at")[:6]
        )
        for idea in idea_qs:
            results.append(_result(
                _("Roadmap"),
                idea.title,
                idea.get_status_display(),
                f"{reverse('roadmap')}?q={query}",
                "fa-solid fa-route",
                idea.get_priority_display(),
                "roadmap-result",
            ))

    return JsonResponse({"results": results[:18]})


@login_required
def inbox_view(request):
    tab = request.GET.get("tab", "all")
    inbox_items = InboxItem.objects.filter(user=request.user)
    if tab == "unread":
        inbox_items = inbox_items.filter(is_read=False)
    elif tab in [choice[0] for choice in InboxItem.TYPE_CHOICES]:
        inbox_items = inbox_items.filter(item_type=tab)

    pending_friendships = []
    pending_skribble_invites = []
    if tab in ("all", "unread", "friend"):
        pending_friendships = Friendship.objects.select_related("from_user", "from_user__profile").filter(
            to_user=request.user,
            status=Friendship.STATUS_PENDING,
        )[:8]
    if tab in ("all", "unread", "skribble"):
        pending_skribble_invites = DrawingGameInvite.objects.select_related("from_user", "lobby").filter(
            to_user=request.user,
            status=DrawingGameInvite.STATUS_PENDING,
        )[:8]

    unread_rooms = []
    if tab in ("all", "unread", "chat"):
        rooms = ChatRoom.objects.filter(room_memberships__user=request.user).prefetch_related("members")[:50]
        for room in rooms:
            membership = room.room_memberships.filter(user=request.user).first()
            qs = room.messages.exclude(sender=request.user)
            if membership and membership.last_read_at:
                qs = qs.filter(created_at__gt=membership.last_read_at)
            unread_count = qs.count()
            if unread_count:
                room.unread_count = unread_count
                room.display_title = room.title_for(request.user)
                unread_rooms.append(room)

    return render(request, "app/inbox.html", {
        "tab": tab,
        "inbox_items": inbox_items[:80],
        "pending_friendships": pending_friendships,
        "pending_skribble_invites": pending_skribble_invites,
        "unread_rooms": unread_rooms,
        "unread_count": InboxItem.objects.filter(user=request.user, is_read=False).count(),
    })


@login_required
@require_POST
def inbox_mark_read_view(request):
    item_id = request.POST.get("item_id")
    qs = InboxItem.objects.filter(user=request.user, is_read=False)
    if item_id and item_id.isdigit():
        qs = qs.filter(id=int(item_id))
    qs.update(is_read=True)
    return redirect(request.POST.get("next") or "inbox")


@login_required
def feedback_view(request):
    if request.method == "POST":
        form = ToolFeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.save()
            InboxItem.objects.create(
                user=request.user,
                item_type=InboxItem.TYPE_FEEDBACK,
                title=_("Feedback gespeichert"),
                message=_("Danke! Dein Feedback wurde in MyTools abgelegt."),
                target_url=reverse("feedback"),
                icon="fa-solid fa-comment-dots",
            )
            return redirect(f"{reverse('feedback')}?sent=1")
    else:
        form = ToolFeedbackForm(initial={"tool_key": request.GET.get("tool", "")})

    # The feedback page has its own confirmation box below.
    # Clear old Django messages here so unrelated messages like
    # "Favoriten wurden aktualisiert" do not show up on the feedback page.
    list(get_messages(request))

    my_feedback = ToolFeedback.objects.filter(user=request.user)[:30]
    open_feedback = ToolFeedback.objects.values("tool_key").annotate(total=Count("id")).order_by("-total")[:8]
    return render(request, "app/feedback.html", {
        "form": form,
        "my_feedback": my_feedback,
        "open_feedback": open_feedback,
        "feedback_sent": request.GET.get("sent") == "1",
    })
