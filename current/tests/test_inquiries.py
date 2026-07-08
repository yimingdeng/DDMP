import uuid

import pytest
from django.urls import reverse

from core.models import PublicationStatus
from inquiries.models import Inquiry, InquiryIntent, InquiryStatus, RegionalContact
from varieties.models import Variety


def make_regional_contact(**overrides):
    data = {
        "area_name": "河南",
        "manager_name": "张经理",
        "role_title": "区域经理",
        "phone": "13800000001",
        "status": PublicationStatus.PUBLISHED,
    }
    data.update(overrides)
    return RegionalContact.objects.create(**data)


def new_submission_key():
    return str(uuid.uuid4())


@pytest.mark.django_db
def test_public_pages_only_show_published_regional_contacts(client):
    make_regional_contact(service_note="负责河南区域服务")
    make_regional_contact(
        area_name="山东",
        manager_name="内部待定人员",
        phone="13800000002",
        status=PublicationStatus.DRAFT,
    )

    response = client.get(reverse("core:home"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "河南" in content
    assert "张经理" in content
    assert "13800000001" in content
    assert "内部待定人员" not in content
    assert "13800000002" not in content


@pytest.mark.django_db
def test_user_can_submit_inquiry_and_admin_data_is_created(client):
    response = client.post(
        reverse("inquiries:submit"),
        {
            "name": "王先生",
            "phone": "139 0000 0001",
            "area_name": "河南",
            "organization": "测试合作社",
            "message": "希望安排看田",
            "privacy_consent": "on",
            "intent_type": InquiryIntent.SITE_VISIT,
            "submission_key": new_submission_key(),
            "next": "/varieties/example/",
        },
    )

    assert response.status_code == 302
    assert response.url == "/varieties/example/#contact"
    inquiry = Inquiry.objects.get()
    assert inquiry.name == "王先生"
    assert inquiry.phone == "139 0000 0001"
    assert inquiry.area_name == "河南"
    assert inquiry.status == InquiryStatus.NEW
    assert inquiry.intent_type == InquiryIntent.SITE_VISIT
    assert inquiry.privacy_consent is True
    assert inquiry.consent_at is not None
    assert inquiry.privacy_version
    assert inquiry.source_path == "/varieties/example/"


@pytest.mark.django_db
def test_inquiry_requires_valid_contact_and_privacy_consent(client):
    response = client.post(
        reverse("inquiries:submit"),
        {
            "name": "测试用户",
            "phone": "abc",
            "area_name": "山东",
            "intent_type": InquiryIntent.CONSULTATION,
            "submission_key": new_submission_key(),
            "next": "/",
        },
        follow=True,
    )

    assert response.status_code == 200
    assert Inquiry.objects.count() == 0
    assert "提交失败" in response.content.decode()


@pytest.mark.django_db
def test_inquiry_does_not_redirect_to_external_next_url(client):
    response = client.post(
        reverse("inquiries:submit"),
        {
            "name": "李女士",
            "phone": "0371-1234567",
            "area_name": "河南",
            "privacy_consent": "on",
            "intent_type": InquiryIntent.CONSULTATION,
            "submission_key": new_submission_key(),
            "next": "https://example.net/steal",
        },
    )

    assert response.status_code == 302
    assert response.url == "/#contact"
    assert Inquiry.objects.get().source_path == "/"


@pytest.mark.django_db
def test_honeypot_submission_is_rejected(client):
    response = client.post(
        reverse("inquiries:submit"),
        {
            "name": "机器人",
            "phone": "13800000001",
            "area_name": "河南",
            "privacy_consent": "on",
            "intent_type": InquiryIntent.CONSULTATION,
            "submission_key": new_submission_key(),
            "website": "https://spam.example",
            "next": "/",
        },
    )

    assert response.status_code == 302
    assert Inquiry.objects.count() == 0


@pytest.mark.django_db
def test_campaign_source_and_variety_are_saved_with_inquiry(client):
    variety = Variety.objects.create(
        name="来源测试品种",
        slug="source-test-variety",
        positioning="来源测试定位",
        summary="来源测试简介",
        status=PublicationStatus.PUBLISHED,
    )
    client.get(reverse("core:home"), {"source": "wechat_moments"})

    response = client.post(
        reverse("inquiries:submit"),
        {
            "name": "来源客户",
            "phone": "13800000009",
            "area_name": "河南",
            "intent_type": InquiryIntent.TRIAL,
            "variety_id": variety.pk,
            "privacy_consent": "on",
            "submission_key": new_submission_key(),
            "next": variety.get_absolute_url(),
        },
    )

    assert response.status_code == 302
    inquiry = Inquiry.objects.get()
    assert inquiry.source_code == "wechat_moments"
    assert inquiry.source_path == "/"
    assert inquiry.variety == variety
    assert inquiry.intent_type == InquiryIntent.TRIAL


@pytest.mark.django_db
def test_repeated_submission_key_does_not_create_duplicate(client):
    key = new_submission_key()
    payload = {
        "name": "防重复客户",
        "phone": "13800000008",
        "area_name": "山东",
        "intent_type": InquiryIntent.AGENCY,
        "privacy_consent": "on",
        "submission_key": key,
        "next": "/",
    }

    first = client.post(reverse("inquiries:submit"), payload)
    second = client.post(reverse("inquiries:submit"), payload)

    assert first.status_code == second.status_code == 302
    assert Inquiry.objects.count() == 1
