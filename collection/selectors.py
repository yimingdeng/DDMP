from django.shortcuts import get_object_or_404

from sites.models import DemoSite

from .models import CollectionReviewer, Observation, ReviewerRole


def accessible_sites(user):
    queryset = DemoSite.objects.select_related("variety")
    if user.is_superuser or user.has_perm("sites.change_demosite"):
        return queryset
    return queryset.filter(collector_assignments__user=user, collector_assignments__is_active=True)


def get_accessible_site(user, pk):
    return get_object_or_404(accessible_sites(user), pk=pk)


def reviewer_for(user):
    if user.is_superuser:
        return {"role": ReviewerRole.HEADQUARTERS, "region": ""}
    reviewer = CollectionReviewer.objects.filter(user=user, is_active=True).first()
    if not reviewer:
        return None
    return {"role": reviewer.role, "region": reviewer.region}


def reviewable_observations(user):
    reviewer = reviewer_for(user)
    if not reviewer:
        return Observation.objects.none()
    queryset = Observation.objects.select_related("site", "site__variety", "created_by")
    if reviewer["role"] == ReviewerRole.REGIONAL:
        queryset = queryset.filter(site__region=reviewer["region"])
    return queryset
