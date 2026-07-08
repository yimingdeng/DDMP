from types import MethodType

from django.contrib import admin

from .models import AuditEvent, SiteConfiguration

admin.site.site_header = "玉米重点品种数字展示平台"
admin.site.site_title = "平台管理"
admin.site.index_title = "平台业务管理"

ADMIN_APP_ORDER = (
    "varieties",
    "sites",
    "media_assets",
    "collection",
    "inquiries",
    "campaigns",
    "analytics",
    "core",
    "auth",
)

ADMIN_MODEL_ORDER = {
    "varieties": ("Variety", "SellingPoint"),
    "sites": ("DemoSite", "Contact"),
    "media_assets": ("MediaAsset",),
    "collection": (
        "DemoApplication",
        "Observation",
        "AnomalyReport",
        "SiteAssignment",
        "CollectionReviewer",
        "PublishedObservation",
        "CollectionEvent",
    ),
    "inquiries": ("Inquiry", "RegionalContact", "InquiryFollowUp"),
    "campaigns": ("ChannelQRCode",),
    "analytics": ("VisitEvent",),
    "core": ("SiteConfiguration", "AuditEvent"),
    "auth": ("User", "Group"),
}


def _order_key(value, preferred_order):
    try:
        return preferred_order.index(value)
    except ValueError:
        return len(preferred_order)


def _get_ordered_app_list(self, request, app_label=None):
    app_dict = self._build_app_dict(request, app_label)
    app_list = list(app_dict.values())
    app_list.sort(
        key=lambda app: (
            _order_key(app["app_label"], ADMIN_APP_ORDER),
            app["name"],
        )
    )
    for app in app_list:
        model_order = ADMIN_MODEL_ORDER.get(app["app_label"], ())
        app["models"].sort(
            key=lambda model: (
                _order_key(model["object_name"], model_order),
                model["name"],
            )
        )
    return app_list


admin.site.get_app_list = MethodType(_get_ordered_app_list, admin.site)


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    fieldsets = (
        ("基本信息", {"fields": ("site_name", "company_name", "logo", "contact_phone")}),
        (
            "首页首屏",
            {
                "fields": (
                    "hero_title",
                    "hero_subtitle",
                    "primary_cta_label",
                    "secondary_cta_label",
                )
            },
        ),
        (
            "分享配置",
            {
                "fields": (
                    "default_share_title",
                    "default_share_description",
                    "default_share_image",
                    "public_base_url",
                )
            },
        ),
        ("地图配置", {"fields": ("amap_js_api_key", "amap_security_code")}),
        ("咨询隐私", {"fields": ("privacy_notice", "privacy_version")}),
        ("页面信息", {"fields": ("meta_description", "footer_text")}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="site_config_change",
            object_type="站点配置",
            object_id=str(obj.pk),
            summary="更新站点配置（未记录字段内容）",
        )


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action_label", "actor", "object_type", "object_id", "summary")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "object_type", "object_id", "summary")
    readonly_fields = ("created_at", "actor", "action", "object_type", "object_id", "summary")

    @admin.display(description="操作")
    def action_label(self, obj):
        return obj.get_action_label()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
