from django.apps import AppConfig


class AkunConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'akun'

    def ready(self):
        from . import signals  # noqa: F401
