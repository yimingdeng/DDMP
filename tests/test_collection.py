from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from collection.forms import ObservationForm
from collection.models import (
    AnomalyReport,
    CollectionEvent,
    CollectionReviewer,
    CollectionStatus,
    DemoApplication,
    DemoApplicationStatus,
    Observation,
    ObservationPhoto,
    ObservationVideo,
    PublishedObservation,
    ReviewerRole,
    SiteAssignment,
)
from core.models import AuditEvent, PublicationStatus
from sites.models import DemoSite, Region
from varieties.models import Variety


def make_site(slug="collector-site"):
    variety = Variety.objects.create(
        name=f"采集品种-{slug}",
        slug=f"variety-{slug}",
        positioning="采集测试定位",
        summary="采集测试简介",
        status=PublicationStatus.PUBLISHED,
    )
    return DemoSite.objects.create(
        name=f"采集示范点-{slug}",
        slug=slug,
        variety=variety,
        region=Region.HUANG_HUAI_HAI,
        province="河南",
        city="郑州",
        county="测试县",
        main_performance="长势整齐",
        description="用于负责人采集流程测试。",
        status=PublicationStatus.PUBLISHED,
    )


def image_upload(name="field.jpg", size=(80, 60)):
    output = BytesIO()
    Image.new("RGB", size, "#4d955a").save(output, "JPEG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/jpeg")


@pytest.mark.django_db
def test_collection_requires_login(client):
    response = client.get(reverse("collection:dashboard"))
    assert response.status_code == 302
    assert reverse("collection:login") in response.url


@pytest.mark.django_db
def test_collection_reviewer_role_clears_irrelevant_region():
    user = get_user_model().objects.create_user("headquarters-role-switch")
    reviewer = CollectionReviewer(
        user=user,
        role=ReviewerRole.HEADQUARTERS,
        region=Region.HUANG_HUAI_HAI,
    )

    reviewer.full_clean()

    assert reviewer.region == ""


@pytest.mark.django_db
def test_collection_login_has_return_to_public_home(client):
    response = client.get(reverse("collection:login"))
    content = response.content.decode()
    assert response.status_code == 200
    assert f'href="{reverse("core:home")}"' in content
    assert "返回展示首页" in content
    assert "第二阶段" not in content
    assert "负责人端" not in content


@pytest.mark.django_db
def test_my_demo_landing_allows_application_without_login(client):
    response = client.get(reverse("collection:landing"))
    content = response.content.decode()
    assert response.status_code == 200
    assert "负责人采集登录" in content
    assert "申请成为示范户" in content
    assert reverse("collection:create-demo-application") in content
    assert "查询申请进度" not in content


@pytest.mark.django_db
def test_demo_application_form_generates_site_name_after_address_fields(client):
    Variety.objects.create(
        name="申请表品种",
        slug="application-form-variety",
        positioning="申请表定位",
        summary="申请表简介",
        status=PublicationStatus.PUBLISHED,
    )

    response = client.get(reverse("collection:create-demo-application"))
    content = response.content.decode()

    assert response.status_code == 200
    assert content.index('name="detailed_address"') < content.index('name="proposed_site_name"')
    assert "默认按“区县 + 乡镇/村”自动生成，也可以手动修改。" in content
    assert "demo-application-form.js?v=20260712-1" in content


@pytest.mark.django_db
def test_login_remembers_username_and_allows_secure_password_autofill(client):
    response = client.get(reverse("collection:login"))
    content = response.content.decode()
    assert 'autocomplete="username"' in content
    assert 'autocomplete="current-password"' in content
    assert "collection-login.js" in content


@pytest.mark.django_db
def test_collection_logout_returns_to_entry_specific_page(client):
    direct_user = get_user_model().objects.create_user("collection-direct", password="123456")
    client.get(reverse("collection:login"))
    client.post(
        reverse("collection:login"),
        {"username": direct_user.username, "password": "123456", "next": ""},
    )

    direct_logout = client.post(reverse("collection:logout"))

    assert direct_logout.status_code == 302
    assert direct_logout.url == reverse("collection:login")

    home_user = get_user_model().objects.create_user("collection-home", password="123456")
    client.get(f"{reverse('collection:landing')}?entry=home")
    client.post(
        reverse("collection:login"),
        {"username": home_user.username, "password": "123456", "next": ""},
    )

    home_logout = client.post(reverse("collection:logout"))

    assert home_logout.status_code == 302
    assert home_logout.url == reverse("core:home")


@pytest.mark.django_db
def test_collector_only_sees_assigned_sites(client):
    user = get_user_model().objects.create_user("collector", password="test-pass-123")
    assigned = make_site("assigned")
    hidden = make_site("hidden")
    SiteAssignment.objects.create(user=user, site=assigned)
    client.force_login(user)

    dashboard = client.get(reverse("collection:dashboard"))
    content = dashboard.content.decode()
    assert assigned.name in content
    assert hidden.name not in content
    assert client.get(reverse("collection:site-tasks", args=(hidden.pk,))).status_code == 404


@pytest.mark.django_db
def test_col_task_001_highlights_current_stage_and_hides_basic_info_edit(client):
    user = get_user_model().objects.create_user("current-task-collector")
    site = make_site("current-task")
    SiteAssignment.objects.create(user=user, site=site)
    Observation.objects.create(
        site=site,
        stage="emergence",
        status=CollectionStatus.DRAFT,
        created_by=user,
        updated_by=user,
    )
    client.force_login(user)

    response = client.get(reverse("collection:site-tasks", args=(site.pk,)))
    content = response.content.decode()

    assert response.status_code == 200
    assert "当前需要采集" in content
    assert "<strong>出苗</strong>" in content
    assert "已有草稿，继续完成采集" in content
    assert "编辑基本信息与定位" not in content
    assert f'href="{reverse("collection:edit-site-basic-info", args=(site.pk,))}"' not in content


def site_basic_info_payload(site, **changes):
    payload = {
        "name": site.name,
        "region": site.region,
        "province": site.province,
        "city": site.city,
        "county": site.county,
        "township_village": site.township_village,
        "detailed_address": site.detailed_address,
        "area_mu": site.area_mu or "",
        "sowing_date": site.sowing_date or "",
        "planting_density": site.planting_density or "",
        "planting_mode": site.planting_mode,
        "latitude": site.latitude or "",
        "longitude": site.longitude or "",
    }
    payload.update(changes)
    return payload


@pytest.mark.django_db
def test_col_site_001_assigned_collector_can_update_site_and_location(client):
    user = get_user_model().objects.create_user("site-editor")
    site = make_site("site-edit")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)
    url = reverse("collection:edit-site-basic-info", args=(site.pk,))

    page = client.get(url)
    assert page.status_code == 200
    assert "定位当前位置" in page.content.decode()
    assert "site-location-form.js" in page.content.decode()

    response = client.post(
        url,
        site_basic_info_payload(
            site,
            name="更新后的示范点",
            township_village="高村乡后侯村",
            area_mu="18.50",
            latitude="34.746600",
            longitude="113.625400",
        ),
    )

    assert response.status_code == 302
    assert response.url == reverse("collection:site-tasks", args=(site.pk,))
    site.refresh_from_db()
    assert site.name == "更新后的示范点"
    assert site.area_mu == Decimal("18.50")
    assert site.latitude == Decimal("34.746600")
    assert site.longitude == Decimal("113.625400")
    event = AuditEvent.objects.get(action="site_basic_info_change")
    assert event.actor == user
    assert event.object_id == str(site.pk)


@pytest.mark.django_db
def test_col_site_001_unassigned_collector_cannot_edit_site(client):
    user = get_user_model().objects.create_user("unassigned-site-editor")
    site = make_site("unassigned-site-edit")
    client.force_login(user)
    url = reverse("collection:edit-site-basic-info", args=(site.pk,))

    assert client.get(url).status_code == 404
    assert client.post(url, site_basic_info_payload(site, name="越权修改")).status_code == 404
    site.refresh_from_db()
    assert site.name != "越权修改"


@pytest.mark.django_db
def test_col_site_001_permissioned_admin_can_edit_any_site(client):
    user = get_user_model().objects.create_user("site-admin", is_staff=True)
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="sites", codename="change_demosite")
    )
    site = make_site("admin-site-edit")
    client.force_login(user)

    page = client.get(reverse("collection:edit-site-basic-info", args=(site.pk,)))

    assert page.status_code == 200
    assert site.name in client.get(reverse("collection:dashboard")).content.decode()


@pytest.mark.django_db
def test_col_site_001_requires_complete_coordinate_pair(client):
    user = get_user_model().objects.create_user("coordinate-validator")
    site = make_site("coordinate-validation")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)

    response = client.post(
        reverse("collection:edit-site-basic-info", args=(site.pk,)),
        site_basic_info_payload(site, latitude="34.746600", longitude=""),
    )

    assert response.status_code == 200
    assert "纬度和经度必须同时填写" in response.content.decode()
    site.refresh_from_db()
    assert site.latitude is None
    assert site.longitude is None


def test_col_site_001_browser_location_converts_wgs84_to_gcj02():
    script = (Path(__file__).parents[1] / "static/js/site-location-form.js").read_text(
        encoding="utf-8"
    )
    assert "navigator.geolocation.getCurrentPosition" in script
    assert "wgs84ToGcj02" in script
    assert "converted.latitude.toFixed(6)" in script
    assert "converted.longitude.toFixed(6)" in script


@pytest.mark.django_db
def test_collector_can_save_incomplete_draft_without_photo(client):
    user = get_user_model().objects.create_user("draft-user")
    site = make_site("draft")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)

    response = client.post(
        reverse("collection:edit-observation", args=(site.pk, "sowing")),
        {"action": "draft", "method": "mechanical", "collector_note": "稍后补充"},
    )
    assert response.status_code == 302
    observation = Observation.objects.get(site=site, stage="sowing")
    assert observation.status == CollectionStatus.DRAFT
    assert observation.data == {"method": "mechanical"}
    assert CollectionEvent.objects.get().action == CollectionStatus.DRAFT


def test_col_std_001_maturity_auto_calculates_lodging_and_disease_levels():
    form = ObservationForm(
        stage="maturity",
        submitting=False,
        data={
            "event_date": "2026-09-10",
            "plant_height": "260",
            "ear_height": "105",
            "lodging_rate": "8",
            "ear_rot_rate": "4",
            "stay_green": "good",
            "dehydration": "fast",
            "ear_quality": "excellent",
        },
    )

    assert form.is_valid(), form.errors
    data = form.observation_data()
    assert data["lodging_level"] == "medium"
    assert data["disease_pressure"] == "medium"

    display = ObservationForm(stage="maturity", initial=data).key_display_rows()
    assert ("倒伏等级（可自动计算）", "中等倒伏") in display
    assert ("病害压力（可自动计算）", "中等") in display


@pytest.mark.django_db
def test_submission_requires_fields_and_photo(client):
    user = get_user_model().objects.create_user("required-user")
    site = make_site("required")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)

    response = client.post(
        reverse("collection:edit-observation", args=(site.pk, "sowing")),
        {"action": "submit", "method": "mechanical"},
    )
    assert response.status_code == 200
    assert "至少需要一张现场照片" in response.content.decode()
    assert Observation.objects.count() == 0


@pytest.mark.django_db
def test_complete_sowing_record_can_be_submitted_and_locked(client):
    user = get_user_model().objects.create_user("submit-user")
    site = make_site("submit")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)
    url = reverse("collection:edit-observation", args=(site.pk, "sowing"))

    response = client.post(
        url,
        {
            "action": "submit",
            "event_date": "2026-06-01",
            "method": "mechanical",
            "density": "4444",
            "row_spacing": "60",
            "area_mu": "20.5",
            "soil_moisture": "suitable",
            "photos": image_upload(size=(2500, 1000)),
            "photo_caption": "播种现场",
        },
    )
    assert response.status_code == 302
    observation = Observation.objects.get(site=site, stage="sowing")
    assert observation.status == CollectionStatus.SUBMITTED
    assert observation.submitted_at is not None
    assert observation.data["area_mu"] == "20.5"
    assert observation.data["plant_spacing"] == "25.0"
    photo = ObservationPhoto.objects.get(observation=observation)
    photo.image.open("rb")
    stored = Image.open(photo.image)
    assert max(stored.size) <= 1920
    assert CollectionEvent.objects.get().action == CollectionStatus.SUBMITTED

    locked = client.post(url, {"action": "draft", "method": "试图修改"})
    assert locked.status_code == 302
    observation.refresh_from_db()
    assert observation.data["method"] == "mechanical"


STAGE_PAYLOADS = {
    "emergence": {
        "event_date": "2026-06-10",
        "emergence_rate": "95",
        "seedling_vigor": "good",
        "uniformity": "good",
        "leaf_color": "green",
        "anomaly": ["none"],
    },
    "jointing": {
        "event_date": "2026-07-01",
        "growth": "good",
        "uniformity": "excellent",
        "plant_type": "compact",
        "leaf_performance": "upright",
        "pest_disease": ["none"],
        "management": ["irrigation"],
    },
    "flowering": {
        "tasseling_date": "2026-07-20",
        "silking_date": "2026-07-22",
        "coordination": "good",
        "tassel_size": "medium",
        "pollen": "normal",
        "silking_uniformity": "good",
        "heat_drought": ["none"],
    },
    "filling": {
        "event_date": "2026-08-10",
        "filling_progress": "normal",
        "stay_green": "good",
        "plant_health": "good",
        "ear_development": "good",
        "pest_disease": ["none"],
        "stress": ["none"],
    },
    "maturity": {
        "event_date": "2026-09-10",
        "plant_height": "260",
        "ear_height": "105",
        "lodging_rate": "1.2",
        "stay_green": "good",
        "dehydration": "fast",
        "ear_quality": "excellent",
    },
    "harvest": {
        "event_date": "2026-09-25",
        "method": "combine",
        "actual_area": "10",
        "actual_weight": "7200",
        "moisture": "25",
        "machine_performance": ["smooth"],
        "commercial_quality": "good",
    },
}


@pytest.mark.django_db
@pytest.mark.parametrize(("stage", "payload"), STAGE_PAYLOADS.items())
def test_each_later_stage_accepts_complete_submission(client, stage, payload):
    user = get_user_model().objects.create_user(f"user-{stage}")
    site = make_site(stage)
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)
    payload = {**payload, "action": "submit", "photos": image_upload(f"{stage}.jpg")}

    response = client.post(reverse("collection:edit-observation", args=(site.pk, stage)), payload)
    assert response.status_code == 302
    observation = Observation.objects.get(site=site, stage=stage)
    assert observation.status == CollectionStatus.SUBMITTED
    if stage == "flowering":
        assert observation.data["flowering_interval_days"] == 2
    if stage == "harvest":
        assert observation.data["actual_yield_kg_mu"] == "720.00"


@pytest.mark.django_db
def test_mobile_form_has_direct_camera_capture(client):
    user = get_user_model().objects.create_user("camera-user")
    site = make_site("camera")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)

    response = client.get(reverse("collection:edit-observation", args=(site.pk, "sowing")))
    content = response.content.decode()
    assert "拍照（可拍多张）" in content
    assert 'capture="environment"' in content
    assert "根据播种密度和行距自动计算" in content


@pytest.mark.django_db
def test_direct_camera_photo_satisfies_submission_requirement(client):
    user = get_user_model().objects.create_user("camera-submit-user")
    site = make_site("camera-submit")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)

    response = client.post(
        reverse("collection:edit-observation", args=(site.pk, "sowing")),
        {
            "action": "submit",
            "event_date": "2026-06-01",
            "method": "mechanical",
            "density": "4800",
            "row_spacing": "60",
            "area_mu": "12",
            "soil_moisture": "suitable",
            "camera_photos": image_upload("camera.jpg"),
        },
    )
    assert response.status_code == 302
    observation = Observation.objects.get(site=site, stage="sowing")
    assert observation.status == CollectionStatus.SUBMITTED
    assert observation.photos.count() == 1


@pytest.mark.django_db
def test_collector_can_record_and_upload_multiple_videos(client):
    user = get_user_model().objects.create_user("video-user")
    site = make_site("video")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)
    video_one = SimpleUploadedFile("field-1.mp4", b"video-one", content_type="video/mp4")
    video_two = SimpleUploadedFile("field-2.mov", b"video-two", content_type="video/quicktime")

    response = client.post(
        reverse("collection:edit-observation", args=(site.pk, "sowing")),
        {
            "action": "draft",
            "method": "mechanical",
            "camera_videos": [video_one, video_two],
            "video_caption": "播种作业视频",
        },
    )
    assert response.status_code == 302
    observation = Observation.objects.get(site=site, stage="sowing")
    assert ObservationVideo.objects.filter(observation=observation).count() == 2


@pytest.mark.django_db
def test_collector_can_report_anomaly_with_required_photo(client):
    user = get_user_model().objects.create_user("anomaly-user")
    site = make_site("anomaly")
    SiteAssignment.objects.create(user=user, site=site)
    client.force_login(user)

    response = client.post(
        reverse("collection:create-anomaly", args=(site.pk,)),
        {
            "stage": "emergence",
            "anomaly_type": "drought",
            "severity": "medium",
            "occurred_date": "2026-07-01",
            "description": "连续高温，表土偏干。",
            "suggested_action": "建议及时浇水。",
            "camera_photos": image_upload("anomaly.jpg"),
        },
    )
    assert response.status_code == 302
    report = AnomalyReport.objects.get(site=site)
    assert report.created_by == user
    assert report.photos.count() == 1


@pytest.mark.django_db
def test_regional_reviewer_cannot_access_other_region(client):
    reviewer_user = get_user_model().objects.create_user("regional-reviewer")
    CollectionReviewer.objects.create(
        user=reviewer_user, role=ReviewerRole.REGIONAL, region=Region.HUANG_HUAI_HAI
    )
    owner = get_user_model().objects.create_user("other-region-owner")
    site = make_site("other-region")
    site.region = Region.SOUTHWEST
    site.save(update_fields=("region",))
    observation = Observation.objects.create(
        site=site,
        stage="sowing",
        status=CollectionStatus.SUBMITTED,
        data={"event_date": "2026-06-01"},
        created_by=owner,
        updated_by=owner,
    )
    client.force_login(reviewer_user)

    response = client.get(reverse("collection:review-observation", args=(observation.pk,)))
    assert response.status_code == 404


@pytest.mark.django_db
def test_two_level_review_publish_and_public_snapshot(client):
    collector = get_user_model().objects.create_user("review-collector")
    regional = get_user_model().objects.create_user("review-regional")
    headquarters = get_user_model().objects.create_user("review-hq")
    site = make_site("review-flow")
    CollectionReviewer.objects.create(user=regional, role=ReviewerRole.REGIONAL, region=site.region)
    CollectionReviewer.objects.create(user=headquarters, role=ReviewerRole.HEADQUARTERS)
    observation = Observation.objects.create(
        site=site,
        stage="sowing",
        status=CollectionStatus.SUBMITTED,
        data={
            "event_date": "2026-06-01",
            "method": "mechanical",
            "density": 4800,
            "row_spacing": "60",
            "plant_spacing": "23.1",
            "area_mu": "20",
            "soil_moisture": "suitable",
            "seed_batch": "内部批次ABC",
            "base_fertilizer": "内部肥料方案",
        },
        collector_note="内部评价",
        created_by=collector,
        updated_by=collector,
    )

    client.force_login(regional)
    response = client.post(
        reverse("collection:review-observation", args=(observation.pk,)),
        {"action": "regional_approve", "comment": "区域数据核验通过。"},
    )
    assert response.status_code == 302
    observation.refresh_from_db()
    assert observation.status == CollectionStatus.REGIONAL_APPROVED

    client.force_login(headquarters)
    response = client.post(
        reverse("collection:review-observation", args=(observation.pk,)),
        {"action": "hq_approve", "comment": "总部复核通过。"},
    )
    assert response.status_code == 302
    observation.refresh_from_db()
    assert observation.status == CollectionStatus.HQ_APPROVED

    response = client.post(
        reverse("collection:review-observation", args=(observation.pk,)),
        {"action": "publish", "public_summary": "播种质量良好，密度符合方案。"},
    )
    assert response.status_code == 302
    observation.refresh_from_db()
    assert observation.status == CollectionStatus.PUBLISHED
    snapshot = PublishedObservation.objects.get(observation=observation)
    assert snapshot.public_summary == "播种质量良好，密度符合方案。"
    assert "seed_batch" not in snapshot.public_data
    assert "base_fertilizer" not in snapshot.public_data

    public_response = client.get(site.get_absolute_url())
    content = public_response.content.decode()
    assert "播种质量良好" in content
    assert "内部批次ABC" not in content
    assert "内部肥料方案" not in content


@pytest.mark.django_db
def test_fe_site_002_public_stages_are_reversed_and_photos_open_in_gallery(client, tmp_path):
    user = get_user_model().objects.create_user("public-stage-user")
    site = make_site("public-stage-order")
    sowing = Observation.objects.create(
        site=site,
        stage="sowing",
        status=CollectionStatus.PUBLISHED,
        data={},
        created_by=user,
        updated_by=user,
    )
    harvest = Observation.objects.create(
        site=site,
        stage="harvest",
        status=CollectionStatus.PUBLISHED,
        data={},
        created_by=user,
        updated_by=user,
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        sowing_photo = ObservationPhoto.objects.create(
            observation=sowing,
            image=image_upload("sowing-public.jpg"),
            caption="播种现场",
            uploaded_by=user,
        )
        harvest_photo = ObservationPhoto.objects.create(
            observation=harvest,
            image=image_upload("harvest-public.jpg"),
            caption="收获现场",
            uploaded_by=user,
        )
        PublishedObservation.objects.create(
            observation=sowing,
            version=1,
            public_data={},
            public_summary="播种阶段详细介绍",
            published_by=user,
        )
        PublishedObservation.objects.create(
            observation=harvest,
            version=1,
            public_data={},
            public_summary="收获阶段详细介绍",
            published_by=user,
        )
        unreviewed_photo = ObservationPhoto.objects.create(
            observation=harvest,
            image=image_upload("after-publication.jpg"),
            caption="尚未审核照片",
            uploaded_by=user,
        )

        response = client.get(site.get_absolute_url())

    content = response.content.decode()
    assert response.status_code == 200
    assert content.index(">收获</h3>") < content.index(">播种</h3>")
    assert content.index(harvest_photo.image.url) < content.index("收获阶段详细介绍")
    assert content.index(sowing_photo.image.url) < content.index("播种阶段详细介绍")
    assert f'href="{harvest_photo.image.url}"' in content
    assert "data-media-gallery" in content
    assert "data-gallery-item" in content
    assert unreviewed_photo.image.url not in content
    site.refresh_from_db()
    assert site.current_stage == "harvest"

    PublishedObservation.objects.create(
        observation=sowing,
        version=2,
        public_data={},
        public_summary="播种阶段补充版本",
        published_by=user,
    )
    site.refresh_from_db()
    assert site.current_stage == "harvest"


@pytest.mark.django_db
def test_rejected_observation_can_be_edited_and_resubmitted(client):
    collector = get_user_model().objects.create_user("rejected-collector")
    regional = get_user_model().objects.create_user("rejected-regional")
    site = make_site("rejected-flow")
    SiteAssignment.objects.create(user=collector, site=site)
    CollectionReviewer.objects.create(user=regional, role=ReviewerRole.REGIONAL, region=site.region)
    observation = Observation.objects.create(
        site=site,
        stage="sowing",
        status=CollectionStatus.SUBMITTED,
        data={"event_date": "2026-06-01"},
        created_by=collector,
        updated_by=collector,
    )
    ObservationPhoto.objects.create(
        observation=observation,
        image=image_upload("existing.jpg"),
        uploaded_by=collector,
    )
    client.force_login(regional)
    client.post(
        reverse("collection:review-observation", args=(observation.pk,)),
        {"action": "reject", "comment": "请核对播种密度。"},
    )
    observation.refresh_from_db()
    assert observation.status == CollectionStatus.REJECTED

    client.force_login(collector)
    response = client.post(
        reverse("collection:edit-observation", args=(site.pk, "sowing")),
        {
            "action": "submit",
            "event_date": "2026-06-01",
            "method": "mechanical",
            "density": "5000",
            "row_spacing": "60",
            "area_mu": "20",
            "soil_moisture": "suitable",
        },
    )
    assert response.status_code == 302
    observation.refresh_from_db()
    assert observation.status == CollectionStatus.SUBMITTED
    assert observation.events.filter(action=CollectionStatus.REJECTED).exists()


@pytest.mark.django_db
def test_user_can_submit_demo_application(client):
    variety = Variety.objects.create(
        name="申请示范品种",
        slug="application-variety",
        positioning="申请定位",
        summary="申请简介",
        status=PublicationStatus.PUBLISHED,
    )
    response = client.post(
        reverse("collection:create-demo-application"),
        {
            "applicant_name": "王小麦",
            "phone": "13800000001",
            "variety": variety.pk,
            "proposed_site_name": "河南申请示范点",
            "region": Region.HUANG_HUAI_HAI,
            "province": "河南省",
            "city": "新乡市",
            "county": "测试县",
            "township_village": "测试乡",
            "detailed_address": "测试村",
            "proposed_area_mu": "30",
            "planned_sowing_date": "2027-06-01",
            "planting_experience": "one_to_three",
            "request_note": "具备灌溉条件。",
        },
    )
    assert response.status_code == 302
    application = DemoApplication.objects.get(applicant__isnull=True)
    assert application.status == DemoApplicationStatus.PENDING
    assert response.url == reverse("collection:login")


@pytest.mark.django_db
def test_demo_application_defaults_site_name_from_county_and_township(client):
    variety = Variety.objects.create(
        name="自动命名示范品种",
        slug="auto-name-application-variety",
        positioning="自动命名定位",
        summary="自动命名简介",
        status=PublicationStatus.PUBLISHED,
    )

    response = client.post(
        reverse("collection:create-demo-application"),
        {
            "applicant_name": "张三",
            "phone": "13800000003",
            "variety": variety.pk,
            "proposed_site_name": "",
            "region": Region.HUANG_HUAI_HAI,
            "province": "河南省",
            "city": "郑州市",
            "county": "荥阳市",
            "township_village": "高村乡后侯村",
            "detailed_address": "1 号地块",
            "proposed_area_mu": "20",
            "planned_sowing_date": "2027-06-01",
            "planting_experience": "first",
            "request_note": "",
        },
    )

    assert response.status_code == 302
    application = DemoApplication.objects.get(phone="13800000003")
    assert application.proposed_site_name == "荥阳市高村乡后侯村"


@pytest.mark.django_db
def test_regional_reviewer_approval_creates_draft_site_and_assignment(client):
    reviewer = get_user_model().objects.create_user("application-reviewer")
    variety = Variety.objects.create(
        name="审核申请品种",
        slug="review-application-variety",
        positioning="审核定位",
        summary="审核简介",
        status=PublicationStatus.PUBLISHED,
    )
    CollectionReviewer.objects.create(
        user=reviewer, role=ReviewerRole.REGIONAL, region=Region.HUANG_HUAI_HAI
    )
    application = DemoApplication.objects.create(
        applicant_name="申请人",
        phone="13800000002",
        variety=variety,
        proposed_site_name="审核后示范点",
        region=Region.HUANG_HUAI_HAI,
        province="河北省",
        city="邯郸市",
        county="测试县",
        proposed_area_mu="25",
        planting_experience="first",
    )
    client.force_login(reviewer)
    response = client.post(
        reverse("collection:review-demo-application", args=(application.pk,)),
        {
            "action": "approve",
            "review_note": "区域条件符合要求。",
            "login_username": "approved-applicant",
            "initial_password": "123456",
        },
    )
    assert response.status_code == 302
    application.refresh_from_db()
    assert application.status == DemoApplicationStatus.APPROVED
    assert application.applicant.username == "approved-applicant"
    assert application.applicant.check_password("123456")
    assert application.created_site.status == PublicationStatus.DRAFT
    assert application.created_site.variety == variety
    assert SiteAssignment.objects.filter(
        user=application.applicant, site=application.created_site, is_active=True
    ).exists()


@pytest.mark.django_db
def test_regional_reviewer_cannot_review_application_from_other_region(client):
    reviewer = get_user_model().objects.create_user("cross-region-reviewer")
    variety = Variety.objects.create(
        name="跨区申请品种",
        slug="cross-region-variety",
        positioning="跨区定位",
        summary="跨区简介",
        status=PublicationStatus.PUBLISHED,
    )
    CollectionReviewer.objects.create(
        user=reviewer, role=ReviewerRole.REGIONAL, region=Region.HUANG_HUAI_HAI
    )
    application = DemoApplication.objects.create(
        applicant_name="跨区申请人",
        phone="13800000003",
        variety=variety,
        proposed_site_name="西南申请示范点",
        region=Region.SOUTHWEST,
        province="四川省",
        city="成都市",
        county="测试县",
        proposed_area_mu="20",
        planting_experience="first",
    )
    client.force_login(reviewer)
    response = client.get(reverse("collection:review-demo-application", args=(application.pk,)))
    assert response.status_code == 404
