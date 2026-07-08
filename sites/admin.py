from django.contrib import admin

from collection.models import SiteAssignment
from core.admin_mixins import PublishableAdminMixin
from media_assets.inlines import MediaAssetInline

from .models import Contact, DemoSite


class SiteAssignmentInline(admin.TabularInline):
    model = SiteAssignment
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "is_active", "assigned_by", "created_at")
    readonly_fields = ("assigned_by", "created_at")


@admin.register(DemoSite)
class DemoSiteAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "sort_order",
        "variety",
        "province",
        "city",
        "current_stage",
        "visiting_status",
        "status",
        "updated_at",
    )
    list_editable = ("sort_order",)
    ordering = ("sort_order", "province", "city", "name")
    list_filter = (
        "status",
        "region",
        "province",
        "current_stage",
        "visiting_status",
        "is_featured",
    )
    search_fields = ("name", "variety__name", "province", "city", "county", "main_performance")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("variety",)
    readonly_fields = ("published_at", "published_by", "created_at", "updated_at")
    inlines = (SiteAssignmentInline, MediaAssetInline)
    fieldsets = (
        ("基础信息", {"fields": ("name", "slug", "variety", "region")}),
        (
            "位置",
            {
                "fields": (
                    ("province", "city", "county"),
                    "township_village",
                    "detailed_address",
                    ("latitude", "longitude"),
                    ("show_township", "show_detailed_address"),
                )
            },
        ),
        (
            "种植信息",
            {
                "fields": (
                    "area_mu",
                    "sowing_date",
                    "planting_density",
                    "planting_mode",
                    "current_stage",
                )
            },
        ),
        ("展示内容", {"fields": ("main_performance", "description", "is_featured")}),
        ("看田预约", {"fields": ("visiting_status", "visiting_note")}),
        (
            "发布",
            {"fields": ("sort_order", "status", "published_at", "published_by")},
        ),
        (
            "内部信息",
            {"classes": ("collapse",), "fields": ("internal_owner", "internal_notes")},
        ),
        ("审计", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, SiteAssignment) and not instance.assigned_by_id:
                instance.assigned_by = request.user
            instance.save()
        for deleted in formset.deleted_objects:
            deleted.delete()
        formset.save_m2m()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from collection.services import synchronize_site_current_stage

        synchronize_site_current_stage(obj.pk)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "role_title", "region", "masked_phone", "show_phone", "is_active")
    list_filter = ("is_active", "show_name", "show_phone")
    search_fields = ("name", "role_title", "region", "phone")
    filter_horizontal = ("sites",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="手机号")
    def masked_phone(self, obj):
        return f"{obj.phone[:3]}****{obj.phone[-4:]}"
