import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


@pytest.mark.django_db
def test_admin_sidebar_follows_business_workflow_order(client):
    admin_user = get_user_model().objects.create_superuser(
        username="navigation-admin",
        password="test-password",
    )
    client.force_login(admin_user)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    app_list = response.context["available_apps"]
    app_labels = [app["app_label"] for app in app_list]
    assert app_labels == [
        "varieties",
        "sites",
        "media_assets",
        "collection",
        "inquiries",
        "campaigns",
        "analytics",
        "core",
        "auth",
    ]

    models_by_app = {
        app["app_label"]: [model["object_name"] for model in app["models"]] for app in app_list
    }
    assert models_by_app["varieties"] == ["Variety", "SellingPoint"]
    assert models_by_app["collection"] == [
        "DemoApplication",
        "Observation",
        "AnomalyReport",
        "SiteAssignment",
        "CollectionReviewer",
        "PublishedObservation",
        "CollectionEvent",
    ]
    assert models_by_app["inquiries"] == ["Inquiry", "RegionalContact", "InquiryFollowUp"]
    assert models_by_app["core"] == ["SiteConfiguration", "AuditEvent"]
    assert models_by_app["auth"] == ["User", "Group"]
