import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0001_initial"),
        ("campaigns", "0002_marketing_packages_and_tracking"),
    ]

    operations = [
        migrations.AddField(model_name="visitevent", name="marketing_package", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="visit_events", to="campaigns.marketingpackage", verbose_name="营销素材")),
        migrations.AddField(model_name="visitevent", name="promotion_identity", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="visit_events", to="campaigns.promotionidentity", verbose_name="推广人")),
        migrations.AddField(model_name="visitevent", name="tracked_link", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="visit_events", to="campaigns.trackedlink", verbose_name="追踪链接")),
    ]
