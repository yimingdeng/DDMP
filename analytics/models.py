from django.db import models


class VisitEvent(models.Model):
    occurred_at = models.DateTimeField("访问时间", auto_now_add=True, db_index=True)
    path = models.CharField("页面路径", max_length=300, db_index=True)
    source_code = models.CharField("来源代码", max_length=40, default="direct", db_index=True)
    visitor_hash = models.CharField("匿名访客标识", max_length=64, db_index=True)
    marketing_package = models.ForeignKey(
        "campaigns.MarketingPackage",
        verbose_name="营销素材",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="visit_events",
    )
    promotion_identity = models.ForeignKey(
        "campaigns.PromotionIdentity",
        verbose_name="推广人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="visit_events",
    )
    tracked_link = models.ForeignKey(
        "campaigns.TrackedLink",
        verbose_name="追踪链接",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="visit_events",
    )

    class Meta:
        verbose_name = "统计工作台"
        verbose_name_plural = "统计工作台"
        ordering = ("-occurred_at",)
        indexes = [models.Index(fields=("occurred_at", "source_code"))]

    def __str__(self):
        return f"{self.path} · {self.occurred_at:%Y-%m-%d %H:%M}"
