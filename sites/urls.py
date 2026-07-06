from django.urls import path

from . import views

app_name = "sites"

urlpatterns = [
    path("", views.site_list, name="list"),
    path("<slug:slug>/", views.site_detail, name="detail"),
]
