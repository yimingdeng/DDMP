from datetime import timedelta

from django.contrib import admin
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from inquiries.models import Inquiry
from media_assets.models import MediaAsset
from sites.models import DemoSite
from varieties.models import Variety

from .models import VisitEvent


@admin.register(VisitEvent)
class VisitEventAdmin(admin.ModelAdmin):
    change_list_template = "admin/analytics/visitevent/change_list.html"
    list_display = (
        "occurred_at",
        "path",
        "source_code",
        "marketing_package",
        "promotion_identity",
        "visitor_short",
    )
    list_filter = ("source_code", "promotion_identity__promoter_type", "occurred_at")
    search_fields = ("path", "source_code")
    date_hierarchy = "occurred_at"
    readonly_fields = (
        "occurred_at",
        "path",
        "source_code",
        "visitor_hash",
        "marketing_package",
        "promotion_identity",
        "tracked_link",
    )

    @admin.display(description="匿名访客")
    def visitor_short(self, obj):
        return obj.visitor_hash[:10]

    def changelist_view(self, request, extra_context=None):
        today = timezone.localdate()
        since_30 = timezone.now() - timedelta(days=30)
        visits = VisitEvent.objects.filter(occurred_at__gte=since_30)
        inquiries = Inquiry.objects.filter(created_at__gte=since_30)
        extra_context = {
            **(extra_context or {}),
            "content_counts": {
                "varieties": Variety.published.count(),
                "sites": DemoSite.published.count(),
                "media": MediaAsset.published.count(),
                "new_inquiries": Inquiry.objects.filter(status="new").count(),
            },
            "pv_7": visits.filter(occurred_at__date__gte=today - timedelta(days=6)).count(),
            "pv_30": visits.count(),
            "uv_30": visits.values("visitor_hash").distinct().count(),
            "daily_visits": (
                visits.annotate(day=TruncDate("occurred_at"))
                .values("day")
                .annotate(total=Count("id"))
                .order_by("day")
            ),
            "top_pages": visits.values("path").annotate(total=Count("id")).order_by("-total")[:10],
            "top_sources": (
                visits.values("source_code").annotate(total=Count("id")).order_by("-total")[:10]
            ),
            "inquiry_statuses": (
                inquiries.values("status").annotate(total=Count("id")).order_by("-total")
            ),
            "inquiry_intents": (
                inquiries.values("intent_type").annotate(total=Count("id")).order_by("-total")
            ),
            "inquiry_sources": (
                inquiries.values("source_code").annotate(total=Count("id")).order_by("-total")[:10]
            ),
            "recent_inquiries": Inquiry.objects.select_related("variety", "demo_site")[:8],
        }
        return super().changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
