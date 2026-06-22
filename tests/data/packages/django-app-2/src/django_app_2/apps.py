from django.apps import AppConfig


__all__ = ("AppConfig",)


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_app_2"
    label = "django_app_2"
