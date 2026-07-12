import uuid

import campaigns.models
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


STAGE_LABELS = {
    "sowing": "播种",
    "emergence": "出苗",
    "jointing": "拔节",
    "flowering": "抽雄吐丝",
    "filling": "灌浆",
    "maturity": "成熟",
    "harvest": "收获",
}


def backfill_marketing_packages(apps, schema_editor):
    Snapshot = apps.get_model("collection", "PublishedObservation")
    Package = apps.get_model("campaigns", "MarketingPackage")
    TrackedLink = apps.get_model("campaigns", "TrackedLink")
    for snapshot in Snapshot.objects.select_related(
        "observation__site__variety"
    ).iterator():
        observation = snapshot.observation
        site = observation.site
        stage_label = STAGE_LABELS.get(observation.stage, observation.stage)
        headline = f"{site.variety.name}｜{site.name}{stage_label}表现更新"
        summary = " ".join((snapshot.public_summary or "").split())[:220]
        package, _ = Package.objects.get_or_create(
            published_observation=snapshot,
            defaults={
                "headline": headline,
                "core_tags": [stage_label, "田间实拍", "持续更新"],
                "wechat_group_copy": f"{headline}\n{summary}\n点击查看完整示范表现。",
                "wechat_channels_title": f"{site.variety.name}{stage_label}田间表现"[:100],
                "wechat_channels_copy": summary,
                "douyin_title": f"实拍{site.variety.name}{stage_label}表现"[:100],
                "douyin_topics": f"#{site.variety.name} #玉米示范 #田间实拍 #{stage_label}",
                "short_video_script": (
                    f"这是{site.variety.name}{site.name}{stage_label}表现。\n"
                    f"{summary}\n想看完整示范表现，请进入数字示范平台。"
                ),
            },
        )
        TrackedLink.objects.get_or_create(
            marketing_package=package,
            source_code="wechat_moments",
            promoter=None,
            defaults={"purpose": "朋友圈海报默认入口"},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0001_initial"),
        ("collection", "0006_sync_demo_site_current_stage"),
    ]

    operations = [
        migrations.CreateModel(
            name="PromotionIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="推广人名称")),
                ("code", models.SlugField(unique=True, verbose_name="内部代码")),
                ("promoter_type", models.CharField(choices=[("sales", "销售人员"), ("dealer", "经销商"), ("site_owner", "示范点负责人")], max_length=20, verbose_name="推广身份")),
                ("region", models.CharField(blank=True, max_length=100, verbose_name="所属区域")),
                ("public_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="公开标识")),
                ("is_active", models.BooleanField(default=True, verbose_name="有效")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
            ],
            options={"verbose_name": "推广身份", "verbose_name_plural": "推广身份", "ordering": ("region", "name")},
        ),
        migrations.AddField(
            model_name="channelqrcode",
            name="published_observation",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="channel_qr_codes", to="collection.publishedobservation", verbose_name="目标阶段表现"),
        ),
        migrations.AlterField(
            model_name="channelqrcode",
            name="target_type",
            field=models.CharField(choices=[("home", "首页"), ("variety", "品种详情"), ("site", "示范点详情"), ("stage", "示范阶段表现"), ("contact", "咨询表单")], max_length=20, verbose_name="目标类型"),
        ),
        migrations.CreateModel(
            name="MarketingPackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="内容标识")),
                ("status", models.CharField(choices=[("ready", "可发布"), ("disabled", "已停用")], db_index=True, default="ready", max_length=20, verbose_name="状态")),
                ("headline", models.CharField(max_length=160, verbose_name="传播标题")),
                ("core_tags", models.JSONField(blank=True, default=list, verbose_name="核心表现标签")),
                ("wechat_group_copy", models.TextField(blank=True, max_length=1000, verbose_name="微信群文案")),
                ("wechat_channels_title", models.CharField(blank=True, max_length=100, verbose_name="视频号标题")),
                ("wechat_channels_copy", models.TextField(blank=True, max_length=1000, verbose_name="视频号文案")),
                ("douyin_title", models.CharField(blank=True, max_length=100, verbose_name="抖音标题")),
                ("douyin_topics", models.CharField(blank=True, max_length=300, verbose_name="抖音话题")),
                ("short_video_script", models.TextField(blank=True, max_length=2000, verbose_name="短视频脚本")),
                ("poster", models.ImageField(blank=True, upload_to=campaigns.models.marketing_poster_path, verbose_name="朋友圈海报")),
                ("video_cover", models.ImageField(blank=True, upload_to=campaigns.models.marketing_video_cover_path, verbose_name="短视频封面")),
                ("generated_at", models.DateTimeField(auto_now_add=True, verbose_name="生成时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("published_observation", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="marketing_package", to="collection.publishedobservation", verbose_name="公开阶段快照")),
            ],
            options={"verbose_name": "营销素材包", "verbose_name_plural": "营销素材包", "ordering": ("-generated_at",)},
        ),
        migrations.CreateModel(
            name="TrackedLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="访问标识")),
                ("source_code", models.CharField(db_index=True, max_length=40, validators=[django.core.validators.RegexValidator("^[a-z0-9][a-z0-9_-]{1,39}$", "来源代码只能包含小写字母、数字、下划线和连字符，长度为 2—40 位。")], verbose_name="渠道来源")),
                ("purpose", models.CharField(blank=True, max_length=200, verbose_name="用途说明")),
                ("is_active", models.BooleanField(default=True, verbose_name="有效")),
                ("click_count", models.PositiveBigIntegerField(default=0, editable=False, verbose_name="访问次数")),
                ("last_clicked_at", models.DateTimeField(blank=True, editable=False, null=True, verbose_name="最近访问")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("marketing_package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tracked_links", to="campaigns.marketingpackage", verbose_name="营销素材包")),
                ("promoter", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tracked_links", to="campaigns.promotionidentity", verbose_name="推广人")),
            ],
            options={
                "verbose_name": "传播追踪链接",
                "verbose_name_plural": "传播追踪链接",
                "ordering": ("-created_at",),
                "constraints": [models.UniqueConstraint(fields=("marketing_package", "source_code", "promoter"), name="unique_package_source_promoter_link")],
            },
        ),
        migrations.RunPython(backfill_marketing_packages, migrations.RunPython.noop),
    ]
