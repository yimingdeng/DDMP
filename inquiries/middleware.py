import re
import uuid

SOURCE_CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")


class CampaignSourceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        source_code = request.GET.get("source", "").strip().lower()
        if SOURCE_CODE_PATTERN.fullmatch(source_code):
            request.session["campaign_source"] = source_code
            request.session["campaign_landing_path"] = request.path[:300]
            request.session.pop("campaign_package_id", None)
            request.session.pop("campaign_promoter_id", None)
            request.session.pop("campaign_tracked_link_id", None)
            content_token = request.GET.get("content", "").strip()
            promoter_token = request.GET.get("promoter", "").strip()
            try:
                uuid.UUID(content_token)
            except (ValueError, TypeError):
                pass
            else:
                from campaigns.models import MarketingPackage, MarketingPackageStatus

                package = (
                    MarketingPackage.objects.select_related(
                        "published_observation__observation__site__variety"
                    )
                    .filter(
                        public_token=content_token,
                        status__in=(
                            MarketingPackageStatus.READY,
                            MarketingPackageStatus.PUBLISHED,
                        ),
                    )
                    .first()
                )
                if package and package.is_publicly_available():
                    request.session["campaign_package_id"] = package.pk
            try:
                uuid.UUID(promoter_token)
            except (ValueError, TypeError):
                pass
            else:
                from campaigns.models import PromotionIdentity

                promoter = PromotionIdentity.objects.filter(
                    public_token=promoter_token, is_active=True
                ).first()
                if promoter:
                    request.session["campaign_promoter_id"] = promoter.pk

        request.campaign_source = request.session.get("campaign_source", "direct")
        request.campaign_landing_path = request.session.get("campaign_landing_path", "")
        request.campaign_package_id = request.session.get("campaign_package_id")
        request.campaign_promoter_id = request.session.get("campaign_promoter_id")
        request.campaign_tracked_link_id = request.session.get("campaign_tracked_link_id")
        return self.get_response(request)
