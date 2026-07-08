import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse

from core.models import PublicationStatus
from varieties.models import SellingPoint, Variety


def make_variety(**overrides):
    data = {
        "name": "测试品种",
        "slug": "test-variety",
        "positioning": "测试定位",
        "summary": "测试品种简介",
        "status": PublicationStatus.PUBLISHED,
    }
    data.update(overrides)
    return Variety.objects.create(**data)


@pytest.mark.django_db
def test_published_manager_hides_drafts():
    published = make_variety()
    make_variety(name="草稿品种", slug="draft-variety", status=PublicationStatus.DRAFT)

    assert list(Variety.published.all()) == [published]


@pytest.mark.django_db
def test_published_variety_requires_positioning_and_summary():
    variety = Variety(
        name="信息不完整品种",
        slug="invalid-variety",
        status=PublicationStatus.PUBLISHED,
    )

    with pytest.raises(ValidationError) as error:
        variety.full_clean()

    assert "positioning" in error.value.message_dict
    assert "summary" in error.value.message_dict


@pytest.mark.django_db
def test_variety_detail_only_shows_published_selling_points(client):
    variety = make_variety(internal_notes="绝不能公开的品种备注")
    SellingPoint.objects.create(
        variety=variety,
        title="公开卖点",
        slug="public-point",
        short_description="公开卖点说明",
        status=PublicationStatus.PUBLISHED,
    )
    SellingPoint.objects.create(
        variety=variety,
        title="草稿卖点",
        slug="draft-point",
        short_description="草稿内容",
        status=PublicationStatus.DRAFT,
    )

    response = client.get(variety.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert "公开卖点" in content
    assert "草稿卖点" not in content
    assert "绝不能公开的品种备注" not in content


@pytest.mark.django_db
def test_draft_variety_returns_404(client):
    variety = make_variety(status=PublicationStatus.DRAFT)

    response = client.get(reverse("varieties:detail", kwargs={"slug": variety.slug}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_variety_detail_prioritizes_mobile_selling_points_and_actions(client):
    """FE-VAR-001/003 and FE-GLOBAL-002: mobile promotion content leads to actions."""
    variety = make_variety(
        suitable_area="河南、山东夏播区",
        maturity="中早熟",
        density_min=4500,
        density_max=5000,
        risk_warning="请根据当地审定区域和气候条件种植。",
        internal_notes="绝不能公开的品种备注",
    )
    SellingPoint.objects.create(
        variety=variety,
        title="抗倒耐密",
        slug="lodging",
        short_description="紧凑株型，适合合理密植。",
        status=PublicationStatus.PUBLISHED,
    )

    response = client.get(variety.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert content.index("一眼看懂品种表现") < content.index("种植关键信息")
    assert 'class="variety-mobile-actions"' in content
    assert 'href="/"><span aria-hidden="true">‹</span>返回</a>' in content
    assert 'href="#regional-contacts">我要咨询</a>' in content
    assert 'href="/sites/"><span aria-hidden="true">⌖</span>看示范</a>' in content
    assert "联系销售" not in content
    assert "种植风险提示" in content
    assert "绝不能公开的品种备注" not in content
    assert "site.css?v=20260707-3" in content
    site_css = (settings.BASE_DIR / "static/css/site.css").read_text(encoding="utf-8")
    assert "grid-template-columns: 108px minmax(0, 1fr);" in site_css
    assert ".variety-selling-points .section-heading.compact h2" in site_css


@pytest.mark.django_db
def test_selling_point_detail_has_contextual_mobile_actions(client):
    """FE-GLOBAL-002: selling-point mobile actions return to the parent variety."""
    variety = make_variety()
    point = SellingPoint.objects.create(
        variety=variety,
        title="抗倒表现",
        slug="lodging-detail",
        short_description="成熟期站秆表现。",
        status=PublicationStatus.PUBLISHED,
    )

    response = client.get(point.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert 'class="selling-point-page has-mobile-action-bar"' in content
    expected_back_link = (
        f'href="{variety.get_absolute_url()}"><span aria-hidden="true">‹</span>返回</a>'
    )
    assert expected_back_link in content
    assert 'href="#regional-contacts">我要咨询</a>' in content
    assert (
        f'href="{variety.get_absolute_url()}#demo-sites"'
        '><span aria-hidden="true">⌖</span>看示范</a>' in content
    )
