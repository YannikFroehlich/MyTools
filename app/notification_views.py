from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .notification_utils import get_notification_counts


@login_required
@never_cache
@require_GET
def notification_counts_api(request):
    return JsonResponse({
        "ok": True,
        "counts": get_notification_counts(request.user),
    })
