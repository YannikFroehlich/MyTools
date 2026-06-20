from django.contrib import messages
from django.contrib.messages import get_messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import NoteForm
from .models import InboxItem, Note


def _accessible_notes_for(user):
    return (
        Note.objects
        .select_related("user")
        .prefetch_related("shared_with")
        .filter(Q(user=user) | Q(shared_with=user))
        .distinct()
    )


def _note_tag_options(notes):
    tags = set()
    for raw_tags in notes.values_list("tags", flat=True):
        for tag in (raw_tags or "").split(","):
            cleaned = tag.strip()
            if cleaned:
                tags.add(cleaned)
    return sorted(tags, key=str.lower)


def _notify_new_note_share(note, sender, recipient_ids):
    if not recipient_ids:
        return

    target_url = f"{reverse('notes')}?scope=shared"
    sender_name = sender.get_full_name() or sender.username
    note_title = note.title or _("Unbenannte Notiz")

    for recipient_id in recipient_ids:
        if recipient_id == sender.id:
            continue
        InboxItem.objects.create(
            user_id=recipient_id,
            item_type=InboxItem.TYPE_SYSTEM,
            title=_("Notiz geteilt"),
            message=_("%(user)s hat eine Notiz mit dir geteilt: %(title)s") % {
                "user": sender_name,
                "title": note_title,
            },
            target_url=target_url,
            icon="fa-regular fa-note-sticky",
        )


def notes_view(request):
    query = request.GET.get("q", "").strip()
    tag_filter = request.GET.get("tag", "").strip()
    scope = request.GET.get("scope", "all").strip()
    show_archived = request.GET.get("archived") == "1"
    valid_scopes = {"all", "mine", "shared", "reminders"}
    if scope not in valid_scopes:
        scope = "all"

    accessible_notes = _accessible_notes_for(request.user)
    active_notes = accessible_notes.filter(is_archived=False)
    notes = accessible_notes.filter(is_archived=show_archived)

    if scope == "mine":
        notes = notes.filter(user=request.user)
    elif scope == "shared":
        notes = notes.filter(shared_with=request.user).exclude(user=request.user)
    elif scope == "reminders":
        notes = notes.filter(reminder_at__isnull=False)

    if tag_filter:
        notes = notes.filter(tags__icontains=tag_filter)

    if query:
        notes = notes.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(tags__icontains=query)
        )

    notes = notes.order_by("-is_pinned", "-updated_at")
    pinned_notes = notes.filter(is_pinned=True)
    normal_notes = notes.filter(is_pinned=False)
    now = timezone.now()

    context = {
        "pinned_notes": pinned_notes,
        "normal_notes": normal_notes,
        "query": query,
        "tag_filter": tag_filter,
        "tag_options": _note_tag_options(active_notes),
        "scope": scope,
        "show_archived": show_archived,
        "note_count": notes.count(),
        "owned_note_count": active_notes.filter(user=request.user).count(),
        "shared_note_count": active_notes.filter(shared_with=request.user).exclude(user=request.user).count(),
        "reminder_note_count": active_notes.filter(reminder_at__isnull=False).count(),
        "due_reminder_count": active_notes.filter(reminder_at__lte=now).count(),
        "archived_note_count": accessible_notes.filter(is_archived=True).count(),
        "note_messages": [
            message for message in get_messages(request)
            if "notes" in message.tags.split()
        ],
    }

    return render(request, "app/notes.html", context)


def note_create_view(request):
    if request.method == "POST":
        form = NoteForm(request.POST, user=request.user)

        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            form.save_m2m()
            _notify_new_note_share(
                note,
                request.user,
                set(note.shared_with.values_list("id", flat=True)),
            )
            messages.success(request, _("Notiz wurde erstellt."), extra_tags="notes")
            return redirect("notes")
    else:
        form = NoteForm(user=request.user)

    return render(request, "app/note_form.html", {
        "form": form,
        "form_title": _("Neue Notiz"),
        "submit_text": _("Notiz speichern"),
    })


def note_edit_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)

    if request.method == "POST":
        previous_shared_ids = set(note.shared_with.values_list("id", flat=True))
        form = NoteForm(request.POST, instance=note, user=request.user)

        if form.is_valid():
            form.save()
            current_shared_ids = set(note.shared_with.values_list("id", flat=True))
            _notify_new_note_share(note, request.user, current_shared_ids - previous_shared_ids)
            messages.success(request, _("Notiz wurde aktualisiert."), extra_tags="notes")
            return redirect("notes")
    else:
        form = NoteForm(instance=note, user=request.user)

    return render(request, "app/note_form.html", {
        "form": form,
        "note": note,
        "form_title": _("Notiz bearbeiten"),
        "submit_text": _("Änderungen speichern"),
    })


def note_detail_view(request, pk):
    note = get_object_or_404(_accessible_notes_for(request.user), pk=pk)

    return render(request, "app/note_detail.html", {
        "note": note,
        "can_edit_note": note.user_id == request.user.id,
    })


@require_POST
def note_delete_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    note.move_to_trash()

    messages.success(request, _("Notiz wurde in den Papierkorb verschoben."), extra_tags="notes")
    return redirect("notes")


@require_POST
def note_toggle_pin_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    note.is_pinned = not note.is_pinned
    note.save()

    return redirect("notes")


@require_POST
def note_toggle_archive_view(request, pk):
    note = get_object_or_404(Note, pk=pk, user=request.user)
    note.is_archived = not note.is_archived
    note.save()

    if note.is_archived:
        messages.success(request, _("Notiz wurde archiviert."), extra_tags="notes")
    else:
        messages.success(request, _("Notiz wurde wiederhergestellt."), extra_tags="notes")

    return redirect("notes")
