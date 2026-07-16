from .settings import *  # noqa: F403


DEBUG = True
MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != "app.middleware.LoginRequiredMiddleware"
]
