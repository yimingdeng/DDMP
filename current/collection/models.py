import uuid
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from PIL import Image, ImageOps

from media_assets.validators import validate_image_upload
from sites.models import DemoSite, GrowthStage, Region
from varieties.models import Variety


class CollectionStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    SUBMITTED = "submitted", "已提交"
    REGIONAL_APPROVED = "regional_approved", "区域审核通过"
    HQ_APPROVED = "hq_approved", "总部审核通过"
    PUBLISHED = "published", "已公开"
    REJECTED = "rejected", "已退回"


class ReviewerRole(models.TextChoices):
    REGIONAL = "regional", "区域审核人"
    HEADQUARTERS = "headquarters", "总部审核人"


class CollectionReviewer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="审核账号",
        on_delete=models.CASCADE,
        related_name="collection_reviewer",
    )
    role = models.CharField("审核角色", max_length=20, choices=ReviewerRole.choices)
    region = models.CharField(
        "负责区域",
        max_length=30,
        choices=Region.choices,
        blank=True,
        help_text="区域审核人必须选择；总部审核人留空。",
    )
    is_active = models.BooleanField("有效", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "采集审核人"
        verbose_name_plural = "采集审核人"

    def __str__(self):
        return f"{self.user.get_username()} · {self.get_role_display()}"

    def clean(self):
        super().clean()
        if self.role == ReviewerRole.REGIONAL and not self.region:
            raise ValidationError({"region": "区域审核人必须选择负责区域。"})
        if self.role == ReviewerRole.HEADQUARTERS:
            self.region = ""


application_phone_validator = RegexValidator(r"^[0-9+()\-\s]{7,30}$", "请输入正确的联系电话。")


class DemoApplicationStatus(models.TextChoices):
    PENDING = "pending", "待区域审核"
    APPROVED = "approved", "已通过"
    REJECTED = "rejected", "已退回"


class PlantingExperience(models.TextChoices):
    FIRST = "first", "首次开展示范"
    ONE_TO_THREE = "one_to_three", "1—3 年"
    OVER_THREE = "over_three", "3 年以上"


class DemoApplication(models.Model):
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="申请人账号",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="demo_applications",
    )
    applicant_name = models.CharField("申请人姓名", max_length=50)
    phone = models.CharField("联系电话", max_length=30, validators=[application_phone_validator])
    variety = models.ForeignKey(
        Variety,
        verbose_name="申请示范品种",
        on_delete=models.PROTECT,
        related_name="demo_applications",
    )
    proposed_site_name = models.CharField("拟建示范点名称", max_length=100)
    region = models.CharField("所属区域", max_length=30, choices=Region.choices, db_index=True)
    province = models.CharField("省份", max_length=50)
    city = models.CharField("城市", max_length=50)
    county = models.CharField("区县", max_length=50)
    township_village = models.CharField("乡镇/村", max_length=100, blank=True)
    detailed_address = models.CharField("详细地址", max_length=200, blank=True)
    proposed_area_mu = models.DecimalField("计划示范面积（亩）", max_digits=10, decimal_places=2)
    planned_sowing_date = models.DateField("计划播种日期", null=True, blank=True)
    planting_experience = models.CharField(
        "示范经验", max_length=30, choices=PlantingExperience.choices
    )
    request_note = models.TextField("申请说明", max_length=1000, blank=True)
    status = models.CharField(
        "审核状态",
        max_length=20,
        choices=DemoApplicationStatus.choices,
        default=DemoApplicationStatus.PENDING,
        db_index=True,
    )
    review_note = models.TextField("审核意见", max_length=1000, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_demo_applications",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    login_username = models.CharField("登录用户名", max_length=150, blank=True, editable=False)
    created_site = models.OneToOneField(
        DemoSite,
        verbose_name="创建的示范点",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="source_application",
    )
    created_at = models.DateTimeField("申请时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "示范申请"
        verbose_name_plural = "示范申请"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.proposed_site_name} · {self.applicant_name} · {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.proposed_area_mu is not None and self.proposed_area_mu <= 0:
            raise ValidationError({"proposed_area_mu": "计划示范面积必须大于 0。"})


class SiteAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="负责人",
        on_delete=models.CASCADE,
        related_name="collection_site_assignments",
    )
    site = models.ForeignKey(
        DemoSite,
        verbose_name="示范点",
        on_delete=models.CASCADE,
        related_name="collector_assignments",
    )
    is_active = models.BooleanField("有效", default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="分配人",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="created_collection_assignments",
    )
    created_at = models.DateTimeField("分配时间", auto_now_add=True)

    class Meta:
        verbose_name = "负责人示范点分配"
        verbose_name_plural = "负责人示范点分配"
        ordering = ("site__province", "site__name", "user__username")
        constraints = [
            models.UniqueConstraint(fields=("user", "site"), name="unique_collector_site")
        ]

    def __str__(self):
        return f"{self.user.get_username()} · {self.site.name}"


class Observation(models.Model):
    site = models.ForeignKey(
        DemoSite,
        verbose_name="示范点",
        on_delete=models.CASCADE,
        related_name="observations",
    )
    stage = models.CharField("采集阶段", max_length=30, choices=GrowthStage.choices)
    status = models.CharField(
        "状态", max_length=20, choices=CollectionStatus.choices, default=CollectionStatus.DRAFT
    )
    data = models.JSONField("采集数据", default=dict, blank=True)
    collector_note = models.TextField("负责人评价", max_length=1000, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.PROTECT,
        related_name="created_observations",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="最近修改人",
        on_delete=models.PROTECT,
        related_name="updated_observations",
    )
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "阶段采集记录"
        verbose_name_plural = "阶段采集记录"
        ordering = ("site", "stage")
        constraints = [
            models.UniqueConstraint(fields=("site", "stage"), name="unique_observation_stage_site")
        ]

    def __str__(self):
        return f"{self.site.name} · {self.get_stage_display()} · {self.get_status_display()}"


def observation_photo_path(instance, filename):
    suffix = Path(filename).suffix.lower() or ".jpg"
    return f"collection/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{suffix}"


def observation_video_path(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"collection/videos/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{suffix}"


def validate_field_video(upload):
    if upload.size <= 0:
        raise ValidationError("视频文件不能为空。")
    if upload.size > 200 * 1024 * 1024:
        raise ValidationError("单个现场视频不能超过 200 MB。")
    if Path(upload.name).suffix.lower() not in {".mp4", ".mov", ".webm"}:
        raise ValidationError("现场视频仅支持 MP4、MOV 或 WebM。")


class ObservationPhoto(models.Model):
    observation = models.ForeignKey(
        Observation,
        verbose_name="采集记录",
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(
        "现场照片", upload_to=observation_photo_path, validators=[validate_image_upload]
    )
    caption = models.CharField("照片说明", max_length=160, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传人",
        on_delete=models.PROTECT,
        related_name="collection_photos",
    )
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        verbose_name = "采集现场照片"
        verbose_name_plural = "采集现场照片"
        ordering = ("uploaded_at",)

    def __str__(self):
        return f"{self.observation} · 照片"

    def save(self, *args, **kwargs):
        if self._state.adding and self.image:
            self.image = self._compressed_image(self.image)
        super().save(*args, **kwargs)

    @staticmethod
    def _compressed_image(upload):
        validate_image_upload(upload)
        upload.seek(0)
        image = ImageOps.exif_transpose(Image.open(upload))
        image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
        if image.mode != "RGB":
            image = image.convert("RGB")
        output = BytesIO()
        image.save(output, format="JPEG", quality=84, optimize=True)
        return ContentFile(output.getvalue(), name=f"{uuid.uuid4().hex}.jpg")


class ObservationVideo(models.Model):
    observation = models.ForeignKey(
        Observation,
        verbose_name="采集记录",
        on_delete=models.CASCADE,
        related_name="videos",
    )
    video = models.FileField(
        "现场视频", upload_to=observation_video_path, validators=[validate_field_video]
    )
    caption = models.CharField("视频说明", max_length=160, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传人",
        on_delete=models.PROTECT,
        related_name="collection_videos",
    )
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        verbose_name = "采集现场视频"
        verbose_name_plural = "采集现场视频"
        ordering = ("uploaded_at",)

    def __str__(self):
        return f"{self.observation} · 视频"

    def save(self, *args, **kwargs):
        if self.video:
            validate_field_video(self.video)
        super().save(*args, **kwargs)


class AnomalyType(models.TextChoices):
    MISSING = "missing", "缺苗"
    PEST = "pest", "虫害"
    DISEASE = "disease", "病害"
    DROUGHT = "drought", "干旱"
    WATERLOGGING = "waterlogging", "涝害"
    LODGING = "lodging", "倒伏/倒折"
    WEATHER = "weather", "高温/风灾/冰雹"
    MANAGEMENT = "management", "管理异常"
    OTHER = "other", "其他"


class AnomalySeverity(models.TextChoices):
    LOW = "low", "轻微"
    MEDIUM = "medium", "中等"
    HIGH = "high", "严重"


class AnomalyStatus(models.TextChoices):
    OPEN = "open", "待处理"
    RESOLVED = "resolved", "已处理"


class AnomalyReport(models.Model):
    site = models.ForeignKey(
        DemoSite, verbose_name="示范点", on_delete=models.CASCADE, related_name="anomaly_reports"
    )
    stage = models.CharField("发生阶段", max_length=30, choices=GrowthStage.choices)
    anomaly_type = models.CharField("异常类型", max_length=30, choices=AnomalyType.choices)
    severity = models.CharField("严重程度", max_length=20, choices=AnomalySeverity.choices)
    occurred_date = models.DateField("发生日期")
    description = models.TextField("情况说明", max_length=1000)
    suggested_action = models.TextField("建议措施", max_length=1000, blank=True)
    status = models.CharField(
        "处理状态", max_length=20, choices=AnomalyStatus.choices, default=AnomalyStatus.OPEN
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上报人",
        on_delete=models.PROTECT,
        related_name="created_anomaly_reports",
    )
    created_at = models.DateTimeField("上报时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "田间异常上报"
        verbose_name_plural = "田间异常上报"
        ordering = ("-occurred_date", "-created_at")

    def __str__(self):
        return f"{self.site} · {self.get_anomaly_type_display()} · {self.get_severity_display()}"


def anomaly_photo_path(instance, filename):
    return f"collection/anomalies/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.jpg"


class AnomalyPhoto(models.Model):
    report = models.ForeignKey(
        AnomalyReport,
        verbose_name="异常记录",
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(
        "异常照片", upload_to=anomaly_photo_path, validators=[validate_image_upload]
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传人",
        on_delete=models.PROTECT,
        related_name="anomaly_photos",
    )
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        verbose_name = "异常照片"
        verbose_name_plural = "异常照片"

    def __str__(self):
        return f"{self.report} · 异常照片"

    def save(self, *args, **kwargs):
        if self._state.adding and self.image:
            self.image = ObservationPhoto._compressed_image(self.image)
        super().save(*args, **kwargs)


class PublishedObservation(models.Model):
    observation = models.ForeignKey(
        Observation,
        verbose_name="原始采集记录",
        on_delete=models.PROTECT,
        related_name="published_versions",
    )
    version = models.PositiveIntegerField("公开版本", default=1)
    public_data = models.JSONField("公开数据", default=dict)
    public_summary = models.TextField("公开摘要", max_length=1000, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="发布人",
        null=True,
        on_delete=models.SET_NULL,
        related_name="published_observations",
    )
    published_at = models.DateTimeField("发布时间", auto_now_add=True)

    class Meta:
        verbose_name = "公开采集快照"
        verbose_name_plural = "公开采集快照"
        ordering = ("observation__site", "observation__stage", "-version")
        constraints = [
            models.UniqueConstraint(
                fields=("observation", "version"), name="unique_observation_public_version"
            )
        ]

    def __str__(self):
        return f"{self.observation} · 公开版本 {self.version}"


class CollectionEvent(models.Model):
    observation = models.ForeignKey(
        Observation,
        verbose_name="采集记录",
        on_delete=models.CASCADE,
        related_name="events",
    )
    action = models.CharField("操作", max_length=30, choices=CollectionStatus.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作人",
        null=True,
        on_delete=models.SET_NULL,
        related_name="collection_events",
    )
    summary = models.TextField("说明", max_length=1000, blank=True)
    created_at = models.DateTimeField("操作时间", auto_now_add=True)

    class Meta:
        verbose_name = "采集操作历史"
        verbose_name_plural = "采集操作历史"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.observation} · {self.get_action_display()}"
