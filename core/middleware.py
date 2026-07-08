class MobilePreviewFrameOptionsMiddleware:
    """Allow only same-origin iframe navigation used by the mobile preview."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        is_preview_frame = (
            request.GET.get("_mobile_frame") == "1"
            or request.headers.get("Sec-Fetch-Dest") == "iframe"
        )
        if is_preview_frame:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response
