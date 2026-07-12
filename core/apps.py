from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "基础配置"

    def ready(self):
        from django.contrib.auth import get_user_model

        from . import signals  # noqa: F401

        UserModel = get_user_model()

        def get_full_name_chinese_order(user):
            full_name = f"{user.last_name}{user.first_name}".strip()
            return full_name or user.username

        def get_short_name_chinese_order(user):
            return user.last_name or user.first_name or user.username

        UserModel.get_full_name = get_full_name_chinese_order
        UserModel.get_short_name = get_short_name_chinese_order
