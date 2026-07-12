from django.urls import path

from . import views

app_name = "sites"

urlpatterns = [
    path("", views.site_list, name="list"),
    path("<slug:slug>/stages/<slug:stage>/", views.stage_detail, name="stage-detail"),
    path(
        "<slug:slug>/stages/<slug:stage>/<uuid:content_token>/",
        views.stage_detail,
        name="stage-content-detail",
    ),
    path("<slug:slug>/", views.site_detail, name="detail"),
]
