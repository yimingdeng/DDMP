from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import ChannelQRCode


@admin.register(ChannelQRCode)
class ChannelQRCodeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "source_code",
        "target_type",
        "target_label",
        "is_active",
        "scan_count",
        "last_scanned_at",
        "qr_actions",
    )
    list_filter = ("is_active", "target_type", "created_at")
    search_fields = (
        "name",
        "source_code",
        "purpose",
        "variety__name",
        "demo_site__name",
    )
    autocomplete_fields = ("variety", "demo_site")
    readonly_fields = (
        "qr_preview",
        "scan_path",
        "target_preview",
        "scan_count",
        "last_scanned_at",
        "created_by",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        ("用途", {"fields": ("name", "purpose", "source_code", "is_active")}),
        ("目标", {"fields": ("target_type", "variety", "demo_site", "target_preview")}),
        ("二维码", {"fields": ("qr_preview", "scan_path")}),
        ("扫码统计", {"fields": ("scan_count", "last_scanned_at")}),
        ("审计", {"classes": ("collapse",), "fields": ("created_by", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="二维码预览")
    def qr_preview(self, obj):
        if not obj.pk:
            return "保存后生成二维码。"
        url = reverse("campaigns-admin:qr-png", kwargs={"pk": obj.pk})
        return format_html('<img src="{}" alt="二维码" style="width:240px;height:240px">', url)

    @admin.display(description="扫码短链接")
    def scan_path(self, obj):
        return obj.get_scan_path() if obj.pk else "保存后生成。"

    @admin.display(description="目标地址")
    def target_preview(self, obj):
        return obj.get_target_url() if obj.pk else "保存后生成。"

    @admin.display(description="操作")
    def qr_actions(self, obj):
        preview = reverse("campaigns-admin:qr-png", kwargs={"pk": obj.pk})
        download = f"{preview}?download=1"
        return format_html(
            '<a href="{}" target="_blank">预览</a> · <a href="{}">下载 PNG</a>',
            preview,
            download,
        )
