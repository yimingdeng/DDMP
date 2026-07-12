from django.urls import path

from . import portal_views

app_name = "marketing"

urlpatterns = [
    path("login/", portal_views.MarketingLoginView.as_view(), name="login"),
    path("logout/", portal_views.marketing_logout, name="logout"),
    path("", portal_views.dashboard, name="dashboard"),
    path("stats/", portal_views.stats_dashboard, name="stats"),
    path("weekly/", portal_views.weekly_report, name="weekly-report"),
    path("<uuid:token>/", portal_views.package_detail, name="package-detail"),
    path("<uuid:token>/prepare/", portal_views.prepare_link, name="prepare-link"),
    path("<uuid:token>/publications/", portal_views.add_publication, name="add-publication"),
    path("<uuid:token>/download.zip", portal_views.download_package, name="download-package"),
    path("links/<uuid:token>/qr.png", portal_views.tracked_link_qr, name="tracked-link-qr"),
]
