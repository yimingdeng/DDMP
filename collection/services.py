from django.db import transaction

from sites.models import DemoSite, GrowthStage

from .models import PublishedObservation

STAGE_RANK = {stage: index for index, (stage, _label) in enumerate(GrowthStage.choices)}


def advance_site_current_stage(site_id, stage):
    """Advance a site's stage without allowing an older stage to regress it."""
    if stage not in STAGE_RANK:
        return False

    with transaction.atomic():
        site = DemoSite.objects.select_for_update().only("current_stage").get(pk=site_id)
        current_rank = STAGE_RANK.get(site.current_stage, -1)
        if STAGE_RANK[stage] <= current_rank:
            return False
        DemoSite.objects.filter(pk=site_id).update(current_stage=stage)
    return True


def synchronize_site_current_stage(site_id):
    """Ensure the stored stage is at least the highest publicly released stage."""
    published_stages = PublishedObservation.objects.filter(
        observation__site_id=site_id
    ).values_list("observation__stage", flat=True)
    highest_stage = max(published_stages, key=lambda stage: STAGE_RANK.get(stage, -1), default=None)
    if highest_stage is None:
        return False
    return advance_site_current_stage(site_id, highest_stage)
