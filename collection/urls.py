from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import CollectorAuthenticationForm

app_name = "collection"

collector_login_view = auth_views.LoginView.as_view(
    template_name="collection/login.html",
    authentication_form=CollectorAuthenticationForm,
)

urlpatterns = [
    path("", collector_login_view, name="landing"),
    path("login/", collector_login_view, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("mine/", views.dashboard, name="dashboard"),
    path("apply/", views.create_demo_application, name="create-demo-application"),
    path("sites/<int:pk>/", views.site_tasks, name="site-tasks"),
    path(
        "sites/<int:pk>/basic-info/",
        views.edit_site_basic_info,
        name="edit-site-basic-info",
    ),
    path("sites/<int:site_pk>/anomalies/new/", views.create_anomaly, name="create-anomaly"),
    path(
        "sites/<int:site_pk>/<slug:stage>/",
        views.edit_observation,
        name="edit-observation",
    ),
    path("photos/<int:pk>/delete/", views.delete_photo, name="delete-photo"),
    path("videos/<int:pk>/delete/", views.delete_video, name="delete-video"),
    path("review/", views.review_queue, name="review-queue"),
    path("review/<int:pk>/", views.review_observation, name="review-observation"),
    path(
        "review/applications/<int:pk>/",
        views.review_demo_application,
        name="review-demo-application",
    ),
]
