from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from sites.models import GrowthStage

from .forms import (
    AnomalyReportForm,
    DemoApplicationForm,
    DemoApplicationReviewForm,
    DemoSiteBasicInfoForm,
    ObservationForm,
    ReviewActionForm,
)
from .models import (
    AnomalyPhoto,
    CollectionEvent,
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
from .selectors import (
    accessible_sites,
    get_accessible_site,
    reviewable_observations,
    reviewer_for,
)
from .stage_fields import STAGE_FIELDS


@login_required
def dashboard(request):
    sites = list(accessible_sites(request.user).prefetch_related("observations"))
    stage_values = list(GrowthStage.choices)
    for site in sites:
        records = {item.stage: item for item in site.observations.all()}
        completed_statuses = {
            CollectionStatus.SUBMITTED,
            CollectionStatus.REGIONAL_APPROVED,
            CollectionStatus.HQ_APPROVED,
            CollectionStatus.PUBLISHED,
        }
        site.collection_progress = []
        for value, label in stage_values:
            record = records.get(value)
            site.collection_progress.append(
                {
                    "value": value,
                    "label": label,
                    "record": record,
                    "is_done": record and record.status in completed_statuses,
                    "is_rejected": record and record.status == CollectionStatus.REJECTED,
                }
            )
        site.completed_count = sum(
            1 for item in records.values() if item.status in completed_statuses
        )
    return render(
        request,
        "collection/dashboard.html",
        {
            "collection_sites": sites,
            "demo_applications": request.user.demo_applications.select_related(
                "variety", "created_site"
            ),
        },
    )


@login_required
def site_tasks(request, pk):
    site = get_accessible_site(request.user, pk)
    records = {item.stage: item for item in site.observations.prefetch_related("photos")}
    tasks = [
        {"value": value, "label": label, "record": records.get(value)}
        for value, label in GrowthStage.choices
    ]
    current_task = next(
        (
            task
            for status in (CollectionStatus.REJECTED, CollectionStatus.DRAFT)
            for task in tasks
            if task["record"] and task["record"].status == status
        ),
        None,
    )
    if current_task is None:
        current_task = next((task for task in tasks if task["record"] is None), None)
    if current_task:
        current_task["is_current"] = True
    events = CollectionEvent.objects.filter(observation__site=site).select_related(
        "observation", "actor"
    )[:30]
    anomalies = site.anomaly_reports.prefetch_related("photos").select_related("created_by")[:20]
    return render(
        request,
        "collection/site_tasks.html",
        {
            "site": site,
            "tasks": tasks,
            "current_task": current_task,
            "collection_events": events,
            "anomaly_reports": anomalies,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_site_basic_info(request, pk):
    from core.models import AuditEvent

    site = get_accessible_site(request.user, pk)
    form = DemoSiteBasicInfoForm(request.POST or None, instance=site)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditEvent.objects.create(
            actor=request.user,
            action="site_basic_info_change",
            object_type="示范点",
            object_id=str(site.pk),
            summary=f"修改示范点基本信息：{site.name}",
        )
        messages.success(request, "示范点基本信息和定位已保存。")
        return redirect("collection:site-tasks", pk=site.pk)
    return render(
        request,
        "collection/site_basic_info_form.html",
        {"site": site, "form": form},
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_observation(request, site_pk, stage):
    if stage not in STAGE_FIELDS:
        return redirect("collection:site-tasks", pk=site_pk)
    site = get_accessible_site(request.user, site_pk)
    observation = (
        Observation.objects.filter(site=site, stage=stage)
        .prefetch_related("photos", "videos")
        .first()
    )
    editable_statuses = {CollectionStatus.DRAFT, CollectionStatus.REJECTED}
    if observation and observation.status not in editable_statuses and request.method == "POST":
        messages.error(request, "该阶段已经提交，不能继续修改。")
        return redirect("collection:site-tasks", pk=site.pk)

    submitting = request.method == "POST" and request.POST.get("action") == "submit"
    initial = {**(observation.data if observation else {})}
    if observation:
        initial["collector_note"] = observation.collector_note
    photo_count = observation.photos.count() if observation else 0
    form = ObservationForm(
        request.POST or None,
        request.FILES or None,
        stage=stage,
        submitting=submitting,
        existing_photo_count=photo_count,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if observation is None:
                observation = Observation(
                    site=site, stage=stage, created_by=request.user, updated_by=request.user
                )
            observation.data = form.observation_data()
            observation.collector_note = form.cleaned_data.get("collector_note", "")
            observation.updated_by = request.user
            observation.status = (
                CollectionStatus.SUBMITTED if submitting else CollectionStatus.DRAFT
            )
            if submitting:
                from django.utils import timezone

                observation.submitted_at = timezone.now()
            observation.save()
            caption = form.cleaned_data.get("photo_caption", "")
            uploaded_photos = list(form.cleaned_data.get("photos", []))
            uploaded_photos = list(form.cleaned_data.get("camera_photos", [])) + uploaded_photos
            for photo in uploaded_photos:
                ObservationPhoto.objects.create(
                    observation=observation,
                    image=photo,
                    caption=caption,
                    uploaded_by=request.user,
                )
            video_caption = form.cleaned_data.get("video_caption", "")
            for video in form.cleaned_data.get("camera_videos", []):
                ObservationVideo.objects.create(
                    observation=observation,
                    video=video,
                    caption=video_caption,
                    uploaded_by=request.user,
                )
            CollectionEvent.objects.create(
                observation=observation,
                action=observation.status,
                actor=request.user,
                summary="提交阶段采集记录" if submitting else "保存采集草稿",
            )
        messages.success(request, "阶段记录已提交。" if submitting else "草稿已保存。")
        return redirect("collection:site-tasks", pk=site.pk)

    return render(
        request,
        "collection/observation_form.html",
        {
            "site": site,
            "stage": stage,
            "stage_label": dict(GrowthStage.choices)[stage],
            "form": form,
            "observation": observation,
            "calculated_data": observation.data if observation else {},
            "display_rows": form.display_rows() if observation else [],
            "can_edit": not observation or observation.status in editable_statuses,
        },
    )


@login_required
@require_POST
def delete_photo(request, pk):
    photo = get_object_or_404(ObservationPhoto.objects.select_related("observation__site"), pk=pk)
    site = get_accessible_site(request.user, photo.observation.site_id)
    if photo.observation.status not in {CollectionStatus.DRAFT, CollectionStatus.REJECTED}:
        messages.error(request, "已提交记录的照片不能删除。")
    else:
        storage = photo.image.storage
        name = photo.image.name
        photo.delete()
        storage.delete(name)
        messages.success(request, "照片已删除。")
    return redirect(
        reverse(
            "collection:edit-observation",
            kwargs={"site_pk": site.pk, "stage": photo.observation.stage},
        )
    )


@login_required
@require_POST
def delete_video(request, pk):
    video = get_object_or_404(ObservationVideo.objects.select_related("observation__site"), pk=pk)
    site = get_accessible_site(request.user, video.observation.site_id)
    stage = video.observation.stage
    if video.observation.status not in {CollectionStatus.DRAFT, CollectionStatus.REJECTED}:
        messages.error(request, "已提交记录的视频不能删除。")
    else:
        storage = video.video.storage
        name = video.video.name
        video.delete()
        storage.delete(name)
        messages.success(request, "视频已删除。")
    return redirect(
        reverse("collection:edit-observation", kwargs={"site_pk": site.pk, "stage": stage})
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_anomaly(request, site_pk):
    site = get_accessible_site(request.user, site_pk)
    form = AnomalyReportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            report = form.save(commit=False)
            report.site = site
            report.created_by = request.user
            report.save()
            photos = list(form.cleaned_data.get("camera_photos", []))
            photos.extend(form.cleaned_data.get("photos", []))
            for photo in photos:
                AnomalyPhoto.objects.create(report=report, image=photo, uploaded_by=request.user)
        messages.success(request, "田间异常已上报。")
        return redirect("collection:site-tasks", pk=site.pk)
    return render(request, "collection/anomaly_form.html", {"site": site, "form": form})


@login_required
def review_queue(request):
    reviewer = reviewer_for(request.user)
    if not reviewer:
        return HttpResponseForbidden("当前账号没有采集审核权限。")
    observations = reviewable_observations(request.user).filter(
        status__in=(
            CollectionStatus.SUBMITTED,
            CollectionStatus.REGIONAL_APPROVED,
            CollectionStatus.HQ_APPROVED,
            CollectionStatus.REJECTED,
            CollectionStatus.PUBLISHED,
        )
    )
    applications = DemoApplication.objects.select_related("applicant", "variety")
    if reviewer["role"] == ReviewerRole.REGIONAL:
        applications = applications.filter(region=reviewer["region"])
    return render(
        request,
        "collection/review_queue.html",
        {
            "reviewer": reviewer,
            "review_observations": observations,
            "demo_applications": applications,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def review_observation(request, pk):
    reviewer = reviewer_for(request.user)
    if not reviewer:
        return HttpResponseForbidden("当前账号没有采集审核权限。")
    observation = get_object_or_404(
        reviewable_observations(request.user).prefetch_related("photos", "videos", "events__actor"),
        pk=pk,
    )
    display_form = ObservationForm(
        stage=observation.stage,
        initial={**observation.data, "collector_note": observation.collector_note},
    )
    form = ReviewActionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        action = form.cleaned_data["action"]
        comment = form.cleaned_data.get("comment", "").strip()
        with transaction.atomic():
            locked = Observation.objects.select_for_update().get(pk=observation.pk)
            next_status = None
            if (
                action == "regional_approve"
                and reviewer["role"] == ReviewerRole.REGIONAL
                and locked.status == CollectionStatus.SUBMITTED
            ):
                next_status = CollectionStatus.REGIONAL_APPROVED
            elif (
                action == "hq_approve"
                and reviewer["role"] == ReviewerRole.HEADQUARTERS
                and locked.status == CollectionStatus.REGIONAL_APPROVED
            ):
                next_status = CollectionStatus.HQ_APPROVED
            elif action == "reject" and (
                (
                    reviewer["role"] == ReviewerRole.REGIONAL
                    and locked.status == CollectionStatus.SUBMITTED
                )
                or (
                    reviewer["role"] == ReviewerRole.HEADQUARTERS
                    and locked.status
                    in {CollectionStatus.REGIONAL_APPROVED, CollectionStatus.HQ_APPROVED}
                )
            ):
                next_status = CollectionStatus.REJECTED
            elif (
                action == "publish"
                and reviewer["role"] == ReviewerRole.HEADQUARTERS
                and locked.status == CollectionStatus.HQ_APPROVED
            ):
                next_status = CollectionStatus.PUBLISHED

            if next_status is None:
                messages.error(request, "当前状态或审核角色不允许执行该操作。")
            else:
                locked.status = next_status
                locked.save(update_fields=("status", "updated_at"))
                CollectionEvent.objects.create(
                    observation=locked,
                    action=next_status,
                    actor=request.user,
                    summary=comment or dict(CollectionStatus.choices)[next_status],
                )
                if next_status == CollectionStatus.PUBLISHED:
                    current_version = (
                        locked.published_versions.aggregate(max_version=Max("version"))[
                            "max_version"
                        ]
                        or 0
                    )
                    excluded = {"seed_batch", "base_fertilizer"}
                    PublishedObservation.objects.create(
                        observation=locked,
                        version=current_version + 1,
                        public_data={
                            key: value for key, value in locked.data.items() if key not in excluded
                        },
                        public_summary=form.cleaned_data["public_summary"].strip(),
                        published_by=request.user,
                    )
                messages.success(request, f"审核状态已更新为：{locked.get_status_display()}。")
                return redirect("collection:review-observation", pk=locked.pk)

    return render(
        request,
        "collection/review_detail.html",
        {
            "reviewer": reviewer,
            "observation": observation,
            "display_rows": display_form.display_rows(),
            "review_form": form,
            "related_anomalies": observation.site.anomaly_reports.filter(
                stage=observation.stage
            ).prefetch_related("photos"),
        },
    )


@require_http_methods(["GET", "POST"])
def create_demo_application(request):
    form = DemoApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "示范申请已提交，后台区域人员审核后会通过电话与您沟通。",
        )
        return redirect("collection:login")
    return render(request, "collection/demo_application_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def review_demo_application(request, pk):
    from django.utils import timezone

    from core.models import PublicationStatus
    from sites.models import DemoSite

    reviewer = reviewer_for(request.user)
    if not reviewer:
        return HttpResponseForbidden("当前账号没有区域审核权限。")
    applications = DemoApplication.objects.select_related("applicant", "variety")
    if not request.user.is_superuser:
        if reviewer["role"] != ReviewerRole.REGIONAL:
            return HttpResponseForbidden("示范申请由区域审核人处理。")
        applications = applications.filter(region=reviewer["region"])
    application = get_object_or_404(applications, pk=pk)
    form = DemoApplicationReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if application.status != DemoApplicationStatus.PENDING:
            messages.error(request, "该申请已经处理，不能重复审核。")
        else:
            with transaction.atomic():
                application = DemoApplication.objects.select_for_update().get(pk=application.pk)
                application.review_note = form.cleaned_data["review_note"].strip()
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                if form.cleaned_data["action"] == "approve":
                    applicant = get_user_model().objects.create_user(
                        username=form.cleaned_data["login_username"].strip(),
                        password=form.cleaned_data["initial_password"],
                        first_name=application.applicant_name,
                    )
                    site = DemoSite.objects.create(
                        name=application.proposed_site_name,
                        slug=f"application-{application.pk}",
                        variety=application.variety,
                        region=application.region,
                        province=application.province,
                        city=application.city,
                        county=application.county,
                        township_village=application.township_village,
                        detailed_address=application.detailed_address,
                        show_township=True,
                        show_detailed_address=False,
                        area_mu=application.proposed_area_mu,
                        sowing_date=application.planned_sowing_date,
                        main_performance="待采集审核后补充",
                        description="示范申请审核通过，田间数据待持续采集。",
                        status=PublicationStatus.DRAFT,
                        internal_owner=application.applicant_name,
                        internal_notes=f"来源：示范申请 #{application.pk}",
                    )
                    SiteAssignment.objects.update_or_create(
                        user=applicant,
                        site=site,
                        defaults={"is_active": True, "assigned_by": request.user},
                    )
                    application.status = DemoApplicationStatus.APPROVED
                    application.applicant = applicant
                    application.login_username = applicant.username
                    application.created_site = site
                else:
                    application.status = DemoApplicationStatus.REJECTED
                application.save()
            messages.success(request, f"示范申请已{application.get_status_display()}。")
            return redirect("collection:review-demo-application", pk=application.pk)
    return render(
        request,
        "collection/demo_application_review.html",
        {"application": application, "review_form": form},
    )
