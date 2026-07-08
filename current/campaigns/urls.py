from django.urls import path

from . import views

app_name = "campaigns-admin"

urlpatterns = [path("qr/<int:pk>.png", views.qr_png, name="qr-png")]
