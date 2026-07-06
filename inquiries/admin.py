from django.contrib import admin
from django.utils import timezone

from core.admin_mixins import PublishableAdminMixin
from core.models import AuditEvent

from .models import Inquiry, InquiryFollowUp, InquiryStatus, RegionalContact


class InquiryFollowUpInline(admin.StackedInline):
    model = InquiryFollowUp
    extra = 0
    fields = ("status", "note", "next_action", "created_by", "created_at")
    readonly_fields = ("created_by", "created_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("created_by")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RegionalContact)
class RegionalContactAdmin(PublishableAdminMixin, admin.ModelAdmin):
    list_display = (
        "area_name",
        "manager_name",
        "role_title",
        "phone",
        "status",
        "sort_order",
        "updated_at",
    )
    list_filter = ("status", "area_name")
    search_fields = ("area_name", "manager_name", "role_title", "phone")
    readonly_fields = ("published_at", "published_by", "created_at", "updated_at")
    fieldsets = (
        ("区域服务", {"fields": ("area_name", "manager_name", "role_title", "phone")}),
        ("公开说明", {"fields": ("service_note",)}),
        ("发布", {"fields": ("sort_order", "status", "published_at", "published_by")}),
        ("审计", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "name",
        "masked_phone",
        "area_name",
        "intent_type",
        "source_code",
        "organization",
        "status",
        "assigned_to",
    )
    list_filter = (
        "status",
        "intent_type",
        "source_code",
        "area_name",
        "variety",
        "demo_site",
        "created_at",
    )
    search_fields = (
        "name",
        "phone",
        "area_name",
        "organization",
        "message",
        "variety__name",
        "demo_site__name",
    )
    autocomplete_fields = ("assigned_to", "variety", "demo_site")
    readonly_fields = (
        "name",
        "phone",
        "area_name",
        "organization",
        "message",
        "intent_type",
        "variety",
        "demo_site",
        "privacy_consent",
        "privacy_version",
        "consent_at",
        "source_code",
        "submission_key",
        "source_path",
        "created_at",
        "updated_at",
        "followed_at",
        "followed_by",
    )
    fields = (
        "status",
        "assigned_to",
        "name",
        "phone",
        "area_name",
        "organization",
        "message",
        "intent_type",
        "variety",
        "demo_site",
        "privacy_consent",
        "privacy_version",
        "consent_at",
        "admin_notes",
        "source_code",
        "submission_key",
        "source_path",
        "followed_at",
        "followed_by",
        "created_at",
        "updated_at",
    )
    actions = ("mark_following", "mark_completed", "mark_invalid")
    inlines = (InquiryFollowUpInline,)

    @admin.display(description="联系电话")
    def masked_phone(self, obj):
        if len(obj.phone) < 7:
            return obj.phone
        return f"{obj.phone[:3]}****{obj.phone[-4:]}"

    def save_model(self, request, obj, form, change):
        if change and {"status", "assigned_to", "admin_notes"} & set(form.changed_data):
            obj.followed_at = timezone.now()
            obj.followed_by = request.user
        super().save_model(request, obj, form, change)
        if change:
            AuditEvent.objects.create(
                actor=request.user,
                action="inquiry_change",
                object_type="咨询记录",
                object_id=str(obj.pk),
                summary="修改线索状态、分配或内部记录",
            )

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, InquiryFollowUp):
                instance.created_by = request.user
                instance.save()
                inquiry = instance.inquiry
                inquiry.status = instance.status
                inquiry.followed_at = instance.created_at or timezone.now()
                inquiry.followed_by = request.user
                inquiry.save(update_fields=("status", "followed_at", "followed_by", "updated_at"))
        formset.save_m2m()

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if object_id and request.method == "GET":
            AuditEvent.objects.create(
                actor=request.user,
                action="inquiry_view",
                object_type="咨询记录",
                object_id=str(object_id),
                summary="查看完整联系方式与线索详情",
            )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def _update_status(self, request, queryset, status):
        now = timezone.now()
        records = list(queryset)
        count = queryset.update(status=status, followed_at=now, followed_by=request.user)
        InquiryFollowUp.objects.bulk_create(
            [
                InquiryFollowUp(
                    inquiry=item,
                    status=status,
                    note="后台批量更新状态",
                    created_by=request.user,
                    created_at=now,
                )
                for item in records
            ]
        )
        self.message_user(request, f"已更新 {count} 条咨询记录。")

    @admin.action(description="标记为跟进中")
    def mark_following(self, request, queryset):
        self._update_status(request, queryset, InquiryStatus.FOLLOWING)

    @admin.action(description="标记为已完成")
    def mark_completed(self, request, queryset):
        self._update_status(request, queryset, InquiryStatus.COMPLETED)

    @admin.action(description="标记为无效线索")
    def mark_invalid(self, request, queryset):
        self._update_status(request, queryset, InquiryStatus.INVALID)

    def has_add_permission(self, request):
        return False


@admin.register(InquiryFollowUp)
class InquiryFollowUpAdmin(admin.ModelAdmin):
    list_display = ("created_at", "inquiry", "status", "created_by", "next_action")
    list_filter = ("status", "created_at")
    search_fields = ("inquiry__name", "note", "next_action", "created_by__username")
    readonly_fields = ("inquiry", "status", "note", "next_action", "created_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
