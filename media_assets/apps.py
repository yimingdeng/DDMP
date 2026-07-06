from django.apps import AppConfig


class MediaAssetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "media_assets"
    verbose_name = "图片与视频"

    def ready(self):
        from . import signals  # noqa: F401
