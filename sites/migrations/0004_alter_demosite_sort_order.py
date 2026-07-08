from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0003_alter_demosite_latitude_alter_demosite_longitude"),
    ]

    operations = [
        migrations.AlterField(
            model_name="demosite",
            name="sort_order",
            field=models.PositiveIntegerField(
                default=100,
                help_text="数字越小越靠前；相同数字再按省份、城市和名称排列。",
                verbose_name="展示顺序",
            ),
        ),
    ]
