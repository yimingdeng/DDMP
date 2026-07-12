import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from analytics.models import VisitEvent
from core.models import AuditEvent
from inquiries.models import Inquiry, InquiryFollowUp, InquiryIntent, InquiryStatus


@pytest.mark.django_db
def test_public_visit_analytics_uses_anonymous_cookie(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert "ddmp_visitor" in response.cookies
    event = VisitEvent.objects.get()
    assert event.path == "/"
    assert event.source_code == "direct"
    assert len(event.visitor_hash) == 64
    assert response.cookies["ddmp_visitor"].value not in event.visitor_hash


@pytest.mark.django_db
def test_privacy_page_is_public_and_notices_anonymous_statistics(client):
    response = client.get(reverse("core:privacy"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "咨询服务隐私说明" in content
    assert "随机匿名标识" in content


@pytest.mark.django_db
def test_inquiry_rate_limit_preserves_safe_values(client):
    cache.clear()
    url = reverse("inquiries:submit")
    for index in range(5):
        client.post(
            url,
            {
                "name": f"客户{index}",
                "phone": "13800000001",
                "area_name": "河南",
                "customer_identity": "farmer",
                "intent_type": InquiryIntent.CONSULTATION,
                "privacy_consent": "on",
                "submission_key": str(uuid.uuid4()),
                "next": "/",
            },
        )
    limited = client.post(
        url,
        {
            "name": "被限流客户",
            "phone": "13800000002",
            "area_name": "山东",
            "customer_identity": "dealer",
            "intent_type": InquiryIntent.TRIAL,
            "privacy_consent": "on",
            "submission_key": str(uuid.uuid4()),
            "next": "/",
        },
        follow=True,
    )
    assert Inquiry.objects.count() == 5
    content = limited.content.decode()
    assert "提交过于频繁" in content
    assert 'value="被限流客户"' in content
    assert 'value="山东"' in content


@pytest.mark.django_db
def test_inquiry_detail_view_creates_sensitive_access_audit(admin_client):
    inquiry = Inquiry.objects.create(
        name="审计客户",
        phone="13800000003",
        area_name="河南",
        intent_type=InquiryIntent.CONSULTATION,
        privacy_consent=True,
    )
    response = admin_client.get(reverse("admin:inquiries_inquiry_change", args=(inquiry.pk,)))
    assert response.status_code == 200
    event = AuditEvent.objects.get(action="inquiry_view")
    assert event.object_id == str(inquiry.pk)
    assert "13800000003" not in event.summary


@pytest.mark.django_db
def test_analytics_dashboard_renders_for_admin(admin_client):
    response = admin_client.get(reverse("admin:analytics_visitevent_changelist"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "统计工作台（最近 30 天）" in content
    assert "30 日估算 UV" in content
    assert "最近线索" in content


@pytest.mark.django_db
def test_follow_up_history_is_linked_to_inquiry():
    user = get_user_model().objects.create_user("follow-user")
    inquiry = Inquiry.objects.create(
        name="跟进客户",
        phone="13800000004",
        area_name="山东",
        intent_type=InquiryIntent.AGENCY,
        privacy_consent=True,
    )
    record = InquiryFollowUp.objects.create(
        inquiry=inquiry,
        status=InquiryStatus.FOLLOWING,
        note="已电话联系",
        next_action="明天发送资料",
        created_by=user,
    )
    assert inquiry.follow_ups.get() == record
    assert record.note == "已电话联系"
