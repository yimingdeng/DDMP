import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from core.admin import PlatformUserChangeForm


@pytest.mark.django_db
def test_adm_auth_002_new_user_gets_generated_required_phone():
    user = get_user_model().objects.create_user(username="generated-phone-user")

    assert user.profile.phone == f"199{user.pk:08d}"


@pytest.mark.django_db
def test_adm_auth_002_login_accepts_username_email_or_phone(client):
    user = get_user_model().objects.create_user(
        username="multi-login-user",
        email="multi-login@example.com",
        password="123456",
    )
    user.profile.phone = "13800001111"
    user.profile.save(update_fields=("phone",))

    for login_identifier in (user.username, user.email, user.profile.phone):
        client.logout()
        response = client.post(
            reverse("collection:login"),
            {"username": login_identifier, "password": "123456", "next": ""},
        )

        assert response.status_code == 302


@pytest.mark.django_db
def test_adm_auth_002_admin_login_accepts_phone_for_permissioned_staff(client):
    user = get_user_model().objects.create_user(
        username="phone-admin-login",
        password="123456",
        is_staff=True,
    )
    user.profile.phone = "13800002222"
    user.profile.save(update_fields=("phone",))
    user.user_permissions.add(Permission.objects.get(codename="view_siteconfiguration"))

    response = client.post(
        reverse("admin:login"),
        {"username": user.profile.phone, "password": "123456", "next": reverse("admin:index")},
    )

    assert response.status_code == 302
    assert response.url == reverse("admin:index")


@pytest.mark.django_db
def test_adm_auth_002_full_name_uses_chinese_order():
    user = get_user_model().objects.create_user(
        username="cn-name-user",
        last_name="邓",
        first_name="康",
    )

    assert user.get_full_name() == "邓康"
    assert user.get_short_name() == "邓"


@pytest.mark.django_db
def test_adm_auth_002_admin_user_form_orders_surname_given_name_and_phone(client):
    admin_user = get_user_model().objects.create_superuser(
        username="identity-admin",
        password="123456",
    )
    target = get_user_model().objects.create_user(
        username="identity-target",
        last_name="张",
        first_name="三",
    )
    target.profile.phone = "13800003333"
    target.profile.save(update_fields=("phone",))
    client.force_login(admin_user)

    response = client.get(reverse("admin:auth_user_change", args=(target.pk,)))
    content = response.content.decode()

    assert response.status_code == 200
    assert "手机" in content
    assert content.index('name="last_name"') < content.index('name="first_name"')
    assert content.index('name="first_name"') < content.index('name="phone"')
    assert "13800003333" in content


@pytest.mark.django_db
def test_adm_auth_002_phone_is_required_in_admin_user_form():
    user = get_user_model().objects.create_user(username="missing-phone-user")
    form = PlatformUserChangeForm(
        instance=user,
        data={
            "username": user.username,
            "last_name": "李",
            "first_name": "四",
            "email": "",
            "phone": "",
            "is_active": "on",
        },
    )

    assert not form.is_valid()
    assert "phone" in form.errors
