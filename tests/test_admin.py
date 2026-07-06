import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import PublicationStatus, SiteConfiguration
from varieties.models import Variety


@pytest.mark.django_db
def test_anonymous_user_is_redirected_from_admin(client):
    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert reverse("admin:login") in response.url


@pytest.mark.django_db
def test_site_configuration_is_a_singleton():
    first = SiteConfiguration.load()
    second = SiteConfiguration(site_name="新的配置")
    second.save()

    assert first.pk == second.pk == 1
    assert SiteConfiguration.objects.count() == 1
    assert SiteConfiguration.objects.get().site_name == "新的配置"


@pytest.mark.django_db
def test_bulk_publish_does_not_publish_incomplete_variety(client):
    user = get_user_model().objects.create_superuser(username="admin", password="test-password")
    valid = Variety.objects.create(
        name="完整品种",
        slug="valid-variety",
        positioning="完整定位",
        summary="完整简介",
    )
    invalid = Variety.objects.create(name="不完整品种", slug="invalid-variety")
    client.force_login(user)

    response = client.post(
        reverse("admin:varieties_variety_changelist"),
        {
            "action": "publish_selected",
            ACTION_CHECKBOX_NAME: [valid.pk, invalid.pk],
            "index": 0,
        },
        follow=True,
    )

    valid.refresh_from_db()
    invalid.refresh_from_db()
    assert response.status_code == 200
    assert valid.status == PublicationStatus.PUBLISHED
    assert valid.published_by == user
    assert invalid.status == PublicationStatus.DRAFT
