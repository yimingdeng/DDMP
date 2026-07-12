import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0002_marketing_packages_and_tracking"),
        ("inquiries", "0003_inquiryfollowup"),
    ]

    operations = [
        migrations.AddField(
            model_name="inquiry",
            name="customer_identity",
            field=models.CharField(choices=[("dealer", "经销商"), ("farmer", "农户"), ("large_grower", "种植大户"), ("cooperative", "合作社"), ("retailer", "零售商"), ("other", "其他")], default="other", max_length=30, verbose_name="客户身份"),
        ),
        migrations.AddField(model_name="inquiry", name="marketing_package", field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inquiries", to="campaigns.marketingpackage", verbose_name="来源营销素材")),
        migrations.AddField(model_name="inquiry", name="promotion_identity", field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inquiries", to="campaigns.promotionidentity", verbose_name="来源推广人")),
        migrations.AddField(model_name="inquiry", name="tracked_link", field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inquiries", to="campaigns.trackedlink", verbose_name="来源追踪链接")),
        migrations.AlterField(model_name="inquiry", name="intent_type", field=models.CharField(choices=[("consultation", "产品咨询"), ("site_visit", "预约看田"), ("trial", "申请试种"), ("agency", "代理合作"), ("event", "参加观摩会"), ("feedback", "提交反馈")], db_index=True, default="consultation", max_length=30, verbose_name="意向类型")),
    ]
