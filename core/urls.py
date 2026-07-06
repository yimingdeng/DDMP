from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("privacy/", views.privacy, name="privacy"),
    path("wechat/js-config/", views.wechat_js_config, name="wechat-js-config"),
]
