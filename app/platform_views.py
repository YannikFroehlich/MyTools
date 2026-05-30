from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .models import ChatRoom, DrawingGameInvite, Friendship, InboxItem, ToolFavorite, ToolFeedback
from .platform_forms import ToolFeedbackForm
from .platform_utils import resolve_tools, tool_by_key


@login_required
def favorites_view(request):
    favorite_keys = set(ToolFavorite.objects.filter(user=request.user).values_list("tool_key", flat=True))
    tools = resolve_tools(request, favorite_keys)
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

    favorite, created = ToolFavorite.objects.get_or_create(user=request.user, tool_key=tool_key)
    is_favorite = True
    if not created:
        favorite.delete()
        is_favorite = False

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "is_favorite": is_favorite})

    messages.success(request, _("Favoriten wurden aktualisiert."))
    return redirect(request.POST.get("next") or "favorites")


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
