from django.db import migrations


STAGE_ORDER = (
    "sowing",
    "emergence",
    "jointing",
    "flowering",
    "filling",
    "maturity",
    "harvest",
)


def sync_demo_site_current_stage(apps, schema_editor):
    del schema_editor
    DemoSite = apps.get_model("sites", "DemoSite")
    PublishedObservation = apps.get_model("collection", "PublishedObservation")
    stage_rank = {stage: index for index, stage in enumerate(STAGE_ORDER)}

    stages_by_site = {}
    rows = PublishedObservation.objects.values_list(
        "observation__site_id", "observation__stage"
    ).iterator()
    for site_id, stage in rows:
        current = stages_by_site.get(site_id)
        if current is None or stage_rank.get(stage, -1) > stage_rank.get(current, -1):
            stages_by_site[site_id] = stage

    for site_id, published_stage in stages_by_site.items():
        site = DemoSite.objects.filter(pk=site_id).only("current_stage").first()
        if site is None:
            continue
        if stage_rank.get(published_stage, -1) > stage_rank.get(site.current_stage, -1):
            DemoSite.objects.filter(pk=site_id).update(current_stage=published_stage)


class Migration(migrations.Migration):
    dependencies = [
        ("collection", "0005_demoapplication_login_username_and_more"),
    ]

    operations = [
        migrations.RunPython(sync_demo_site_current_stage, migrations.RunPython.noop),
    ]
