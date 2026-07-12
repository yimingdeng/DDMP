from django.contrib import admin, messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    ChannelQRCode,
    ExternalPublication,
    MarketingPackage,
    MarketingPackageStatus,
    MarketingPosterVariant,
    MarketingWeeklyReport,
    PromotionIdentity,
    ShortVideoTopic,
    TrackedLink,
)
from .services import refresh_marketing_package


@admin.register(PromotionIdentity)
class PromotionIdentityAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "promoter_type", "region", "user", "is_active")
    list_filter = ("promoter_type", "is_active", "region")
    search_fields = ("name", "code", "region")
    autocomplete_fields = ("user",)
    readonly_fields = ("public_token", "created_at")


class ShortVideoTopicInline(admin.TabularInline):
    model = ShortVideoTopic
    extra = 0
    fields = ("sort_order", "is_active", "focus", "title", "script")


class ExternalPublicationInline(admin.TabularInline):
    model = ExternalPublication
    extra = 0
    fields = (
        "channel",
        "status",
        "title",
        "account_name",
        "external_url",
        "published_at",
        "view_count",
        "like_count",
        "comment_count",
        "share_count",
    )
    readonly_fields = ("created_by", "created_at", "updated_at")


class MarketingPosterVariantInline(admin.TabularInline):
    model = MarketingPosterVariant
    extra = 0
    fields = (
        "variant_type",
        "title",
        "promoter",
        "tracked_link",
        "image_preview",
        "is_active",
    )
    readonly_fields = ("image_preview",)

    @admin.display(description="预览")
    def image_preview(self, obj):
        if not obj.image:
            return "尚未生成。"
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" alt="{}" '
            'style="width:120px;height:auto"></a>',
            obj.image.url,
            obj.image.url,
            obj.get_variant_type_display(),
        )


@admin.register(MarketingPackage)
class MarketingPackageAdmin(admin.ModelAdmin):
    change_form_template = "admin/campaigns/marketingpackage/change_form.html"
    inlines = (ShortVideoTopicInline, MarketingPosterVariantInline, ExternalPublicationInline)
    list_display = (
        "headline",
        "stage_label",
        "site_label",
        "status",
        "has_poster",
        "generated_at",
    )
    list_filter = (
        "status",
        "published_observation__observation__stage",
        "published_observation__observation__site__region",
    )
    search_fields = (
        "headline",
        "published_observation__observation__site__name",
        "published_observation__observation__site__variety__name",
    )
    raw_id_fields = ("published_observation",)
    readonly_fields = (
        "public_token",
        "poster_preview",
        "video_cover_preview",
        "poster_variants_preview",
        "public_page",
        "share_pack",
        "reviewed_by",
        "reviewed_at",
        "published_at",
        "generated_at",
        "updated_at",
    )
    actions = (
        "mark_ready",
        "mark_published",
        "mark_disabled",
        "regenerate_materials",
    )
    fieldsets = (
        ("内容来源", {"fields": ("published_observation", "status", "public_token")}),
        ("核心内容", {"fields": ("headline", "core_tags")}),
        (
            "微信",
            {
                "fields": (
                    "wechat_moments_copy",
                    "customer_private_copy",
                    "wechat_group_copy",
                    "wechat_channels_title",
                    "wechat_channels_copy",
                )
            },
        ),
        (
            "抖音与视频",
            {"fields": ("douyin_title", "douyin_topics", "short_video_script")},
        ),
        (
            "生成素材",
            {
                "fields": (
                    "poster_preview",
                    "video_cover_preview",
                    "poster_variants_preview",
                    "public_page",
                    "share_pack",
                )
            },
        ),
        (
            "审核与时间",
            {
                "classes": ("collapse",),
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "published_at",
                    "generated_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_urls(self):
        custom_urls = [
            path(
                "<path:object_id>/generate-materials/",
                self.admin_site.admin_view(self.generate_materials_view),
                name="campaigns_marketingpackage_generate_materials",
            )
        ]
        return custom_urls + super().get_urls()

    def generate_materials_view(self, request, object_id):
        if request.method != "POST":
            return HttpResponseNotAllowed(("POST",))
        package = self.get_object(request, object_id)
        if package is None or not self.has_change_permission(request, package):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        try:
            refresh_marketing_package(package)
        except Exception:
            self.message_user(
                request,
                "素材生成失败，请检查公开图片、媒体目录写入权限和站点公网地址。",
                level=messages.ERROR,
            )
        else:
            self.message_user(request, "朋友圈海报、短视频封面和传播文案已重新生成。")
        return redirect("admin:campaigns_marketingpackage_change", package.pk)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, ExternalPublication) and obj.created_by_id is None:
                obj.created_by = request.user
            obj.save()
        formset.save_m2m()
        for obj in formset.deleted_objects:
            obj.delete()

    @admin.display(description="阶段")
    def stage_label(self, obj):
        return obj.observation.get_stage_display()

    @admin.display(description="示范点")
    def site_label(self, obj):
        return obj.observation.site.name

    @admin.display(description="海报", boolean=True)
    def has_poster(self, obj):
        return bool(obj.poster)

    @admin.display(description="朋友圈海报")
    def poster_preview(self, obj):
        if not obj.poster:
            return "尚未生成，可使用列表页“重新生成素材”。"
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" alt="朋友圈海报" '
            'style="width:240px;height:auto"></a>',
            obj.poster.url,
            obj.poster.url,
        )

    @admin.display(description="短视频封面")
    def video_cover_preview(self, obj):
        if not obj.video_cover:
            return "尚未生成。"
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" alt="短视频封面" '
            'style="width:180px;height:auto"></a>',
            obj.video_cover.url,
            obj.video_cover.url,
        )

    @admin.display(description="海报模板")
    def poster_variants_preview(self, obj):
        if not obj.pk:
            return "保存后使用。"
        variants = obj.poster_variants.filter(is_active=True)[:6]
        if not variants:
            return "尚未生成海报模板。"
        links = []
        for variant in variants:
            if variant.image:
                links.append(
                    format_html(
                        '<a href="{}" target="_blank">{}</a>',
                        variant.image.url,
                        variant.get_variant_type_display(),
                    )
                )
        return format_html(" · ".join(str(link) for link in links)) if links else "尚未生成图片。"

    @admin.display(description="阶段传播页面")
    def public_page(self, obj):
        return format_html('<a href="{}" target="_blank">打开阶段页面</a>', obj.get_absolute_url())

    @admin.display(description="一键转发包")
    def share_pack(self, obj):
        if not obj.pk:
            return "保存后使用。"
        url = reverse("marketing:package-detail", kwargs={"token": obj.public_token})
        return format_html('<a class="button" href="{}" target="_blank">打开营销发布中心</a>', url)

    @admin.action(description="审核通过：标记为可发布")
    def mark_ready(self, request, queryset):
        count = queryset.exclude(status=MarketingPackageStatus.DISABLED).update(
            status=MarketingPackageStatus.READY,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f"已将 {count} 个素材包标记为可发布。")

    @admin.action(description="登记为已发布")
    def mark_published(self, request, queryset):
        count = queryset.filter(
            status__in=(MarketingPackageStatus.READY, MarketingPackageStatus.PUBLISHED)
        ).update(status=MarketingPackageStatus.PUBLISHED, published_at=timezone.now())
        self.message_user(request, f"已登记 {count} 个素材包为已发布。")

    @admin.action(description="停用所选营销素材")
    def mark_disabled(self, request, queryset):
        count = queryset.update(status=MarketingPackageStatus.DISABLED)
        self.message_user(request, f"已停用 {count} 个营销素材包。")

    @admin.action(description="重新生成所选素材的文案、海报和封面")
    def regenerate_materials(self, request, queryset):
        completed = 0
        for package in queryset.select_related("published_observation__observation__site__variety"):
            try:
                refresh_marketing_package(package)
            except Exception:
                self.message_user(
                    request,
                    f"{package} 生成失败，请检查公开图片和站点公网地址。",
                    level=messages.ERROR,
                )
            else:
                completed += 1
        if completed:
            self.message_user(request, f"已重新生成 {completed} 个营销素材包。")


@admin.register(ShortVideoTopic)
class ShortVideoTopicAdmin(admin.ModelAdmin):
    list_display = ("title", "marketing_package", "focus", "sort_order", "is_active")
    list_filter = ("is_active", "marketing_package__published_observation__observation__stage")
    search_fields = ("title", "focus", "marketing_package__headline")
    autocomplete_fields = ("marketing_package",)


@admin.register(ExternalPublication)
class ExternalPublicationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "channel",
        "status",
        "account_name",
        "published_at",
        "view_count",
        "engagement_count",
        "marketing_package",
    )
    list_filter = ("channel", "status", "published_at")
    search_fields = ("title", "account_name", "external_url", "marketing_package__headline")
    autocomplete_fields = ("marketing_package",)
    readonly_fields = ("created_by", "created_at", "updated_at", "engagement_count")
    fieldsets = (
        ("发布内容", {"fields": ("marketing_package", "channel", "status", "title")}),
        ("平台信息", {"fields": ("account_name", "external_url", "published_at")}),
        ("人工回填指标", {"fields": ("view_count", "like_count", "comment_count", "share_count")}),
        ("备注与审计", {"fields": ("notes", "created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="互动量")
    def engagement_count(self, obj):
        return obj.engagement_count

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(MarketingPosterVariant)
class MarketingPosterVariantAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "variant_type",
        "marketing_package",
        "promoter",
        "tracked_link",
        "is_active",
        "updated_at",
    )
    list_filter = ("variant_type", "is_active")
    search_fields = (
        "title",
        "subtitle",
        "marketing_package__headline",
        "promoter__name",
    )
    autocomplete_fields = ("marketing_package", "promoter", "tracked_link")
    readonly_fields = ("public_token", "image_preview", "generated_at", "updated_at")
    fieldsets = (
        ("模板", {"fields": ("marketing_package", "variant_type", "is_active")}),
        ("内容", {"fields": ("title", "subtitle", "call_to_action")}),
        ("专属链接", {"fields": ("promoter", "tracked_link")}),
        ("图片", {"fields": ("image_preview", "image")}),
        (
            "审计",
            {"classes": ("collapse",), "fields": ("public_token", "generated_at", "updated_at")},
        ),
    )

    @admin.display(description="预览")
    def image_preview(self, obj):
        if not obj.image:
            return "尚未生成。"
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" alt="{}" '
            'style="width:180px;height:auto"></a>',
            obj.image.url,
            obj.image.url,
            obj.get_variant_type_display(),
        )


@admin.register(MarketingWeeklyReport)
class MarketingWeeklyReportAdmin(admin.ModelAdmin):
    list_display = ("title", "start_date", "end_date", "is_archived", "created_by", "updated_at")
    list_filter = ("is_archived", "start_date")
    search_fields = ("title", "summary", "recommended_actions")
    readonly_fields = ("created_by", "created_at", "updated_at")
    date_hierarchy = "start_date"

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TrackedLink)
class TrackedLinkAdmin(admin.ModelAdmin):
    list_display = (
        "marketing_package",
        "source_code",
        "promoter",
        "is_active",
        "click_count",
        "last_clicked_at",
    )
    list_filter = ("source_code", "is_active", "promoter__promoter_type")
    search_fields = ("marketing_package__headline", "source_code", "promoter__name")
    autocomplete_fields = ("marketing_package", "promoter")
    readonly_fields = ("token", "scan_path", "click_count", "last_clicked_at", "created_at")

    @admin.display(description="传播短链接")
    def scan_path(self, obj):
        return obj.get_scan_path() if obj.pk else "保存后生成。"


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
        "published_observation__observation__site__name",
    )
    autocomplete_fields = ("variety", "demo_site", "published_observation")
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
        (
            "目标",
            {
                "fields": (
                    "target_type",
                    "variety",
                    "demo_site",
                    "published_observation",
                    "target_preview",
                )
            },
        ),
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
