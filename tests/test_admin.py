import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from core.models import PublicationStatus, SiteColorTheme, SiteConfiguration
from varieties.models import Variety


@pytest.mark.django_db
def test_anonymous_user_is_redirected_from_admin(client):
    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert reverse("admin:login") in response.url


@pytest.mark.django_db
def test_admin_login_rejects_staff_without_admin_permissions(client):
    user = get_user_model().objects.create_user(
        username="staff-without-admin-perms",
        password="test-password",
        is_staff=True,
    )

    response = client.post(
        reverse("admin:login"),
        {"username": user.username, "password": "test-password", "next": reverse("admin:index")},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "当前账号没有后台管理权限" in content
    assert "你没有查看或编辑的权限" not in content
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_admin_index_redirects_logged_in_staff_without_admin_permissions(client):
    user = get_user_model().objects.create_user(
        username="logged-staff-without-admin-perms",
        password="test-password",
        is_staff=True,
    )
    client.force_login(user)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert reverse("admin:login") in response.url


@pytest.mark.django_db
def test_admin_login_allows_staff_with_registered_admin_permission(client):
    user = get_user_model().objects.create_user(
        username="staff-with-admin-perm",
        password="test-password",
        is_staff=True,
    )
    user.user_permissions.add(Permission.objects.get(codename="view_siteconfiguration"))

    response = client.post(
        reverse("admin:login"),
        {"username": user.username, "password": "test-password", "next": reverse("admin:index")},
    )

    assert response.status_code == 302
    assert response.url == reverse("admin:index")


@pytest.mark.django_db
def test_admin_logout_returns_to_admin_login(client):
    user = get_user_model().objects.create_superuser(
        username="logout-admin",
        password="test-password",
    )
    client.force_login(user)

    response = client.post("/admin/logout/")

    assert response.status_code == 302
    assert response.url == reverse("admin:login")
    assert reverse("collection:login") not in response.url


@pytest.mark.django_db
def test_site_configuration_is_a_singleton():
    first = SiteConfiguration.load()
    second = SiteConfiguration(site_name="新的配置")
    second.save()

    assert first.pk == second.pk == 1
    assert SiteConfiguration.objects.count() == 1
    assert SiteConfiguration.objects.get().site_name == "新的配置"


@pytest.mark.django_db
def test_fe_theme_001_admin_can_configure_supported_color_themes(client):
    user = get_user_model().objects.create_superuser(
        username="theme-admin",
        password="test-password",
    )
    configuration = SiteConfiguration.load()
    client.force_login(user)

    response = client.get(reverse("admin:core_siteconfiguration_change", args=(configuration.pk,)))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'name="color_theme"' in content
    assert f'value="{SiteColorTheme.SYSTEM}"' in content
    assert f'value="{SiteColorTheme.PURPLE_YELLOW}"' in content


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
