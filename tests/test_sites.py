import pytest
from django.conf import settings
from django.contrib import admin
from django.urls import reverse

from core.models import PublicationStatus, SiteConfiguration
from sites.models import Contact, DemoSite, Region, VisitingStatus
from varieties.models import Variety


@pytest.fixture
def published_variety(db):
    return Variety.objects.create(
        name="示范测试品种",
        slug="site-test-variety",
        positioning="示范定位",
        summary="示范简介",
        status=PublicationStatus.PUBLISHED,
    )


def make_site(variety, **overrides):
    data = {
        "name": "河南示范点",
        "slug": "henan-site",
        "variety": variety,
        "region": Region.HUANG_HUAI_HAI,
        "province": "河南省",
        "city": "新乡市",
        "county": "测试县",
        "township_village": "测试乡镇",
        "detailed_address": "不得公开的内部详细地址",
        "show_township": True,
        "show_detailed_address": False,
        "main_performance": "公开表现",
        "description": "公开介绍",
        "status": PublicationStatus.PUBLISHED,
        "visiting_status": VisitingStatus.OPEN,
        "internal_notes": "不得公开的内部备注",
    }
    data.update(overrides)
    return DemoSite.objects.create(**data)


@pytest.mark.django_db
def test_site_list_filters_by_region(client, published_variety):
    make_site(published_variety)
    make_site(
        published_variety,
        name="西南示范点",
        slug="southwest-site",
        region=Region.SOUTHWEST,
        province="四川省",
    )

    response = client.get(reverse("sites:list"), {"region": Region.SOUTHWEST})
    content = response.content.decode()

    assert response.status_code == 200
    assert "西南示范点" in content
    assert "河南示范点" not in content


@pytest.mark.django_db
def test_fe_site_001_public_list_uses_admin_display_order(client, published_variety):
    later_site = make_site(
        published_variety,
        name="排序靠后示范点",
        slug="later-display-site",
        sort_order=200,
    )
    earlier_site = make_site(
        published_variety,
        name="排序靠前示范点",
        slug="earlier-display-site",
        sort_order=10,
    )

    response = client.get(reverse("sites:list"))
    content = response.content.decode()

    assert content.index(earlier_site.name) < content.index(later_site.name)


def test_adm_site_001_order_is_editable_from_admin_list():
    site_admin = admin.site._registry[DemoSite]

    assert "sort_order" in site_admin.list_display
    assert site_admin.list_editable == ("sort_order",)
    assert site_admin.ordering[:1] == ("sort_order",)


@pytest.mark.django_db
def test_fe_site_004_defaults_to_huang_huai_hai_all_provinces(client, published_variety):
    make_site(published_variety)
    make_site(
        published_variety,
        name="西南示范点",
        slug="southwest-default-site",
        region=Region.SOUTHWEST,
        province="四川省",
    )

    response = client.get(reverse("sites:list"))
    content = response.content.decode()

    assert response.context["selected_region"] == Region.HUANG_HUAI_HAI
    assert response.context["selected_province"] == ""
    assert "河南示范点" in content
    assert "西南示范点" not in content
    assert 'name="region"' not in content
    assert 'name="province"' not in content
    assert "黄淮海 · 附近示范" in content
    assert "四川省" not in content


@pytest.mark.django_db
def test_fe_site_004_allows_explicit_all_regions(client, published_variety):
    make_site(published_variety)
    make_site(
        published_variety,
        name="西南示范点",
        slug="southwest-all-site",
        region=Region.SOUTHWEST,
        province="四川省",
    )

    response = client.get(reverse("sites:list"), {"region": "", "province": ""})
    content = response.content.decode()

    assert "河南示范点" in content
    assert "西南示范点" in content


@pytest.mark.django_db
def test_site_detail_respects_address_and_internal_privacy(client, published_variety):
    site = make_site(published_variety)

    response = client.get(site.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert "测试乡镇" in content
    assert "不得公开的内部详细地址" not in content
    assert "不得公开的内部备注" not in content
    assert 'class="site-detail-page has-mobile-action-bar"' in content
    assert f'href="{reverse("sites:list")}"><span aria-hidden="true">‹</span>返回</a>' in content
    assert 'href="#regional-contacts">我要咨询</a>' in content
    assert 'href="#inquiry"><span aria-hidden="true">⌖</span>预约看田</a>' in content
    assert 'class="side-panel visit-panel" id="inquiry"' in content


@pytest.mark.django_db
def test_site_detail_only_displays_public_contact_fields(client, published_variety):
    site = make_site(published_variety)
    private_contact = Contact.objects.create(
        name="内部人员",
        phone="13800000001",
        show_name=False,
        show_phone=False,
    )
    private_contact.sites.add(site)
    public_contact = Contact.objects.create(
        name="公开联系人",
        phone="13800000002",
        show_name=True,
        show_phone=False,
    )
    public_contact.sites.add(site)

    response = client.get(site.get_absolute_url())
    content = response.content.decode()

    assert "公开联系人" in content
    assert "13800000002" not in content
    assert "内部人员" not in content
    assert "13800000001" not in content


@pytest.mark.django_db
def test_draft_site_is_not_public(client, published_variety):
    site = make_site(published_variety, status=PublicationStatus.DRAFT)

    response = client.get(site.get_absolute_url())

    assert response.status_code == 404


@pytest.mark.django_db
def test_fe_site_004_supports_pin_map_and_corrected_nearest_location(client, published_variety):
    configuration = SiteConfiguration.load()
    configuration.amap_js_api_key = "test-amap-key"
    configuration.amap_security_code = "test-security-code"
    configuration.save()
    site = make_site(
        published_variety,
        latitude="34.746600",
        longitude="113.625400",
    )

    response = client.get(reverse("sites:list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert ">列表</button>" in content
    assert ">地图</button>" in content
    assert 'class="active" data-site-view="map" aria-pressed="true"' in content
    assert 'class="site-list-view" data-site-panel="list" hidden' in content
    assert '<div class="site-map-view" data-site-panel="map">' in content
    assert "正在获取您的位置，为您查找最近的示范点" in content
    assert 'id="site-map"' in content
    assert "site-map.js" in content
    assert "site-map.js?v=20260705-4" in content
    assert "test-amap-key" in content
    assert "test-security-code" in content
    assert "leaflet" not in content.lower()
    assert site.get_absolute_url() in content
    assert "34.7466" in content
    assert "113.6254" in content
    assert "不得公开的内部详细地址" not in content
    assert "navigator.geolocation.getCurrentPosition" in (
        settings.BASE_DIR / "static/js/site-map.js"
    ).read_text(encoding="utf-8")
    map_script = (settings.BASE_DIR / "static/js/site-map.js").read_text(encoding="utf-8")
    assert 'AMap.convertFrom([longitude, latitude], "gps"' in map_script
    assert "const marker = new AMap.Marker({" in map_script
    assert "createMarkerContent" not in map_script
    assert "title.textContent = `${site.name}${distanceText}`" in map_script
    assert 'link.textContent = "查看详情"' in map_script
    assert "site.location" not in map_script
    assert "desktopProvinceZoom + Math.log2(mapWidth / desktopMapWidth)" in map_script
    assert "siteMap.setZoomAndCenter(getProvinceViewZoom(), position, true)" in map_script
    assert "window.requestAnimationFrame(applyCenter)" in map_script
    site_css = (settings.BASE_DIR / "static/css/site.css").read_text(encoding="utf-8")
    assert "grid-template-columns: 106px minmax(0, 1fr);" in site_css
    assert ".site-detail-page .site-detail-hero" in site_css
    assert ".site-detail-page .data-grid" in site_css
    assert 'class="site-list-page has-mobile-action-bar"' in content
    assert f'href="{reverse("core:home")}"><span aria-hidden="true">‹</span>返回</a>' in content
    assert 'href="#regional-contacts">我要咨询</a>' in content
    assert (
        f'href="{published_variety.get_absolute_url()}"'
        '><span aria-hidden="true">▦</span>看详情</a>' in content
    )


@pytest.mark.django_db
def test_site_without_coordinates_remains_in_list_with_map_notice(client, published_variety):
    make_site(published_variety)

    response = client.get(reverse("sites:list"))
    content = response.content.decode()

    assert "河南示范点" in content
    assert "尚未配置经纬度" in content
