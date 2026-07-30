import hashlib
import time
from dataclasses import dataclass

from django.core.cache import cache


@dataclass(frozen=True)
class RateLimitRule:
    scope: str
    limit: int
    window_seconds: int
    methods: frozenset[str]


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int
    limit: int
    remaining: int


RATE_LIMIT_RULES = {
    "login": RateLimitRule("auth-login", 10, 5 * 60, frozenset({"POST"})),
    "two_factor_verify": RateLimitRule("auth-two-factor", 5, 5 * 60, frozenset({"POST"})),
    "signup": RateLimitRule("auth-signup", 5, 15 * 60, frozenset({"POST"})),
    "password_reset": RateLimitRule("auth-password-reset", 5, 15 * 60, frozenset({"POST"})),
    "chat_send": RateLimitRule("chat-send", 45, 60, frozenset({"POST"})),
    "file_share_upload": RateLimitRule("file-share-upload", 10, 60 * 60, frozenset({"POST"})),
    "file_converter": RateLimitRule("file-converter", 20, 60 * 60, frozenset({"POST"})),
    "feedback": RateLimitRule("feedback", 10, 60 * 60, frozenset({"POST"})),
    "roadmap": RateLimitRule("roadmap", 30, 60 * 60, frozenset({"POST"})),
    "genius-search-api": RateLimitRule("genius-api", 60, 10 * 60, frozenset({"GET"})),
    "tankstellen-api": RateLimitRule("fuel-api", 60, 10 * 60, frozenset({"GET"})),
    "shopping-product-api": RateLimitRule("shopping-product-api", 10, 60, frozenset({"GET"})),
}

DEFAULT_POST_API_RULE = RateLimitRule("post-api", 300, 60, frozenset({"POST"}))


def rule_for_request(url_name, method):
    if not url_name:
        return None

    method = method.upper()
    rule = RATE_LIMIT_RULES.get(url_name)
    if rule and method in rule.methods:
        return rule

    if method == "POST" and (url_name.endswith("_api") or url_name.endswith("-api")):
        return RateLimitRule(f"post-api:{url_name}", DEFAULT_POST_API_RULE.limit, DEFAULT_POST_API_RULE.window_seconds, DEFAULT_POST_API_RULE.methods)

    return None


def _client_identity(request):
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False):
        return f"user:{user.pk}"

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',', 1)[0].strip()}"

    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def _ip_identity(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',', 1)[0].strip()}"
    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def _identities_for_rule(request, rule):
    if rule.scope != "auth-two-factor":
        return (_client_identity(request),)

    identities = [_ip_identity(request)]
    session = getattr(request, "session", None)
    pending_user_id = session.get("two_factor_user_id") if session is not None else None
    if pending_user_id:
        identities.append(f"pending-user:{pending_user_id}")
    return tuple(identities)


def check_rate_limit(request, rule):
    user = getattr(request, "user", None)
    if getattr(user, "is_staff", False):
        return RateLimitResult(True, 0, rule.limit, rule.limit)

    now = int(time.time())
    bucket = now // rule.window_seconds
    retry_after = max(((bucket + 1) * rule.window_seconds) - now, 1)
    counts = []
    for identity in _identities_for_rule(request, rule):
        raw_key = f"{rule.scope}:{identity}:{bucket}"
        key = "rate-limit:" + hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        cache.add(key, 0, timeout=rule.window_seconds + 60)
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=rule.window_seconds + 60)
            count = 1
        counts.append(count)

    highest_count = max(counts, default=0)
    remaining = max(rule.limit - highest_count, 0)
    return RateLimitResult(highest_count <= rule.limit, retry_after, rule.limit, remaining)
