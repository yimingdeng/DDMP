from django.urls import path

from . import views

app_name = "varieties"

urlpatterns = [
    path("<slug:slug>/", views.variety_detail, name="detail"),
    path(
        "<slug:variety_slug>/selling-points/<slug:slug>/",
        views.selling_point_detail,
        name="selling-point-detail",
    ),
]
