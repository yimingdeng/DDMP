from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("varieties/", include("varieties.urls")),
    path("sites/", include("sites.urls")),
    path("inquiries/", include("inquiries.urls")),
    path("campaigns/", include("campaigns.urls")),
    path("q/", include("campaigns.public_urls")),
    path("analytics/", include("analytics.urls")),
    path("collection/", include("collection.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
