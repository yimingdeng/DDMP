import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0002_marketing_packages_and_tracking"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="marketingpackage",
            name="published_at",
            field=models.DateTimeField(
                blank=True, editable=False, null=True, verbose_name="登记发布时间"
            ),
        ),
        migrations.AddField(
            model_name="marketingpackage",
            name="reviewed_at",
            field=models.DateTimeField(
                blank=True, editable=False, null=True, verbose_name="审核时间"
            ),
        ),
        migrations.AddField(
            model_name="marketingpackage",
            name="reviewed_by",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviewed_marketing_packages",
                to=settings.AUTH_USER_MODEL,
                verbose_name="审核人",
            ),
        ),
        migrations.AddField(
            model_name="promotionidentity",
            name="user",
            field=models.OneToOneField(
                blank=True,
                help_text="绑定后，该账号可登录营销发布中心获取专属链接和二维码。",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="promotion_identity",
                to=settings.AUTH_USER_MODEL,
                verbose_name="登录账号",
            ),
        ),
        migrations.AlterField(
            model_name="marketingpackage",
            name="status",
            field=models.CharField(
                choices=[
                    ("generated", "待审核"),
                    ("ready", "可发布"),
                    ("published", "已登记发布"),
                    ("disabled", "已停用"),
                ],
                db_index=True,
                default="generated",
                max_length=20,
                verbose_name="状态",
            ),
        ),
    ]
