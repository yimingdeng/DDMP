from django.contrib import admin
from django.utils.html import format_html

from core.admin_mixins import PublishableAdminMixin

from .models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = (
        "preview",
        "title",
        "media_type",
        "target_label",
        "is_cover",
        "sort_order",
        "status",
        "updated_at",
    )
    list_filter = ("media_type", "status", "is_cover", "content_type")
    search_fields = ("title", "description", "alt_text", "video_url")
    readonly_fields = (
        "preview_large",
        "thumbnail",
        "file_size",
        "mime_type",
        "checksum_sha256",
        "video_file_size",
        "video_mime_type",
        "video_checksum_sha256",
        "published_at",
        "published_by",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        ("关联内容", {"fields": ("content_type", "object_id", "media_type")}),
        ("文字信息", {"fields": ("title", "description", "alt_text", "captured_at")}),
        ("图片", {"fields": ("image", "video_cover", "thumbnail", "preview_large")}),
        ("外部视频链接", {"fields": ("video_platform", "video_url")}),
        ("本地视频", {"fields": ("video_file",)}),
        ("展示控制", {"fields": ("is_cover", "sort_order", "status")}),
        (
            "文件信息",
            {
                "classes": ("collapse",),
                "fields": (
                    "file_size",
                    "mime_type",
                    "checksum_sha256",
                    "video_file_size",
                    "video_mime_type",
                    "video_checksum_sha256",
                ),
            },
        ),
        (
            "审计",
            {
                "classes": ("collapse",),
                "fields": ("published_at", "published_by", "created_at", "updated_at"),
            },
        ),
    )

    @admin.display(description="预览")
    def preview(self, obj):
        image = obj.display_image
        if not image:
            return "—"
        return format_html(
            '<img src="{}" alt="" '
            'style="width:64px;height:44px;object-fit:cover;border-radius:6px">',
            image.url,
        )

    @admin.display(description="大图预览")
    def preview_large(self, obj):
        image = obj.display_image
        if not image:
            return "暂无图片"
        return format_html(
            '<img src="{}" alt="" style="max-width:480px;max-height:300px;object-fit:contain">',
            image.url,
        )
