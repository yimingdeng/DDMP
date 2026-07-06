from django.contrib import admin

from .models import (
    AnomalyPhoto,
    AnomalyReport,
    CollectionEvent,
    CollectionReviewer,
    DemoApplication,
    Observation,
    ObservationPhoto,
    ObservationVideo,
    PublishedObservation,
    SiteAssignment,
)


@admin.register(CollectionReviewer)
class CollectionReviewerAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "region", "is_active", "created_at")
    list_filter = ("role", "region", "is_active")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)


@admin.register(DemoApplication)
class DemoApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "proposed_site_name",
        "applicant_name",
        "region",
        "variety",
        "status",
        "reviewed_by",
    )
    list_filter = ("status", "region", "province", "created_at")
    search_fields = (
        "proposed_site_name",
        "applicant_name",
        "phone",
        "province",
        "city",
        "county",
        "variety__name",
    )
    readonly_fields = (
        "applicant",
        "applicant_name",
        "phone",
        "variety",
        "proposed_site_name",
        "region",
        "province",
        "city",
        "county",
        "township_village",
        "detailed_address",
        "proposed_area_mu",
        "planned_sowing_date",
        "planting_experience",
        "request_note",
        "status",
        "review_note",
        "reviewed_by",
        "reviewed_at",
        "created_site",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SiteAssignment)
class SiteAssignmentAdmin(admin.ModelAdmin):
    list_display = ("site", "user", "is_active", "assigned_by", "created_at")
    list_filter = ("is_active", "site__province", "created_at")
    search_fields = ("site__name", "user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("site", "user")
    readonly_fields = ("assigned_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not obj.assigned_by_id:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)


class ObservationPhotoInline(admin.TabularInline):
    model = ObservationPhoto
    extra = 0
    fields = ("image", "caption", "uploaded_by", "uploaded_at")
    readonly_fields = fields
    can_delete = False


class CollectionEventInline(admin.TabularInline):
    model = CollectionEvent
    extra = 0
    fields = ("action", "summary", "actor", "created_at")
    readonly_fields = fields
    can_delete = False


class ObservationVideoInline(admin.TabularInline):
    model = ObservationVideo
    extra = 0
    fields = ("video", "caption", "uploaded_by", "uploaded_at")
    readonly_fields = fields
    can_delete = False


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ("site", "stage", "status", "created_by", "submitted_at", "updated_at")
    list_filter = ("status", "stage", "site__province", "submitted_at")
    search_fields = ("site__name", "site__variety__name", "created_by__username")
    readonly_fields = (
        "site",
        "stage",
        "status",
        "data",
        "collector_note",
        "created_by",
        "updated_by",
        "submitted_at",
        "created_at",
        "updated_at",
    )
    inlines = (ObservationPhotoInline, ObservationVideoInline, CollectionEventInline)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"}

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CollectionEvent)
class CollectionEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "observation", "action", "actor", "summary")
    list_filter = ("action", "created_at")
    search_fields = ("observation__site__name", "actor__username", "summary")
    readonly_fields = ("observation", "action", "actor", "summary", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AnomalyPhotoInline(admin.TabularInline):
    model = AnomalyPhoto
    extra = 0
    readonly_fields = ("image", "uploaded_by", "uploaded_at")
    can_delete = False


@admin.register(AnomalyReport)
class AnomalyReportAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_date",
        "site",
        "stage",
        "anomaly_type",
        "severity",
        "status",
        "created_by",
    )
    list_filter = ("status", "severity", "anomaly_type", "stage", "site__region")
    search_fields = ("site__name", "description", "suggested_action", "created_by__username")
    readonly_fields = (
        "site",
        "stage",
        "anomaly_type",
        "severity",
        "occurred_date",
        "description",
        "suggested_action",
        "created_by",
        "created_at",
        "updated_at",
    )
    inlines = (AnomalyPhotoInline,)

    def has_add_permission(self, request):
        return False


@admin.register(PublishedObservation)
class PublishedObservationAdmin(admin.ModelAdmin):
    list_display = ("observation", "version", "published_by", "published_at")
    list_filter = ("observation__stage", "observation__site__region", "published_at")
    search_fields = ("observation__site__name", "public_summary")
    readonly_fields = (
        "observation",
        "version",
        "public_data",
        "public_summary",
        "published_by",
        "published_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
