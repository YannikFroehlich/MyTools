from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    name = 'app'

    def ready(self):
        from . import signals  # noqa: F401
