from django.urls import path

from . import views

app_name = "campaigns"

urlpatterns = [path("<uuid:token>/", views.scan_redirect, name="scan")]
