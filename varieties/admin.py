from django.contrib import admin

from core.admin_mixins import PublishableAdminMixin
from media_assets.inlines import MediaAssetInline

from .models import SellingPoint, Variety


class SellingPointInline(admin.TabularInline):
    model = SellingPoint
    extra = 0
    fields = ("title", "point_type", "short_description", "sort_order", "status")
    show_change_link = True


@admin.register(Variety)
class VarietyAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "approval_number",
        "maturity",
        "status",
        "is_featured",
        "updated_at",
    )
    list_filter = ("status", "is_featured", "maturity")
    search_fields = ("name", "approval_number", "positioning", "suitable_area")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("published_at", "published_by", "created_at", "updated_at")
    inlines = (SellingPointInline, MediaAssetInline)
    fieldsets = (
        ("基础信息", {"fields": ("name", "slug", "positioning", "summary")}),
        (
            "正式信息",
            {
                "fields": (
                    "approval_number",
                    "suitable_area",
                    "maturity",
                    "plant_type",
                    "ear_type",
                    "grain_type",
                    ("density_min", "density_max"),
                )
            },
        ),
        (
            "栽培与风险",
            {
                "fields": (
                    "sowing_advice",
                    "water_fertilizer_management",
                    "cultivation_points",
                    "risk_warning",
                )
            },
        ),
        (
            "发布",
            {
                "fields": (
                    "is_featured",
                    "sort_order",
                    "status",
                    "published_at",
                    "published_by",
                )
            },
        ),
        ("内部信息", {"classes": ("collapse",), "fields": ("internal_notes",)}),
        ("审计", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )


@admin.register(SellingPoint)
class SellingPointAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = ("title", "variety", "point_type", "sort_order", "status", "updated_at")
    list_filter = ("status", "point_type", "variety")
    search_fields = ("title", "short_description", "variety__name")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("variety",)
    readonly_fields = ("published_at", "published_by", "created_at", "updated_at")
    inlines = (MediaAssetInline,)
    fieldsets = (
        ("基础信息", {"fields": ("variety", "title", "slug", "point_type")}),
        ("展示内容", {"fields": ("short_description", "detail", "data_note")}),
        ("发布", {"fields": ("sort_order", "status", "published_at", "published_by")}),
        ("内部依据", {"classes": ("collapse",), "fields": ("internal_basis",)}),
        ("审计", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )
