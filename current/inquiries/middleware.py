import re

SOURCE_CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")


class CampaignSourceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        source_code = request.GET.get("source", "").strip().lower()
        if SOURCE_CODE_PATTERN.fullmatch(source_code):
            request.session["campaign_source"] = source_code
            request.session["campaign_landing_path"] = request.path[:300]

        request.campaign_source = request.session.get("campaign_source", "direct")
        request.campaign_landing_path = request.session.get("campaign_landing_path", "")
        return self.get_response(request)
