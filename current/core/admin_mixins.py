from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PublicationStatus


class PublishableAdminMixin:
    actions = ("publish_selected", "archive_selected", "return_to_draft")

    def save_model(self, request, obj, form, change):
        if obj.status == PublicationStatus.PUBLISHED:
            if obj.published_at is None:
                obj.published_at = timezone.now()
            obj.published_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="发布所选内容")
    def publish_selected(self, request, queryset):
        published_count = 0
        invalid_items = []
        for obj in queryset:
            obj.status = PublicationStatus.PUBLISHED
            obj.published_at = obj.published_at or timezone.now()
            obj.published_by = request.user
            try:
                obj.full_clean()
            except ValidationError:
                invalid_items.append(str(obj))
                continue
            obj.save()
            published_count += 1

        if published_count:
            self.message_user(request, f"已发布 {published_count} 条内容。")
        if invalid_items:
            names = "、".join(invalid_items[:5])
            suffix = "等" if len(invalid_items) > 5 else ""
            self.message_user(
                request,
                f"以下内容信息不完整，未发布：{names}{suffix}",
                level=messages.ERROR,
            )

    @admin.action(description="归档所选内容")
    def archive_selected(self, request, queryset):
        count = queryset.update(status=PublicationStatus.ARCHIVED)
        self.message_user(request, f"已归档 {count} 条内容。")

    @admin.action(description="将所选内容退回草稿")
    def return_to_draft(self, request, queryset):
        count = queryset.update(status=PublicationStatus.DRAFT)
        self.message_user(request, f"已将 {count} 条内容退回草稿。")
