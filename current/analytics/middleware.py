import hashlib
import uuid

from django.db import DatabaseError

from .models import VisitEvent


class PublicVisitMiddleware:
    COOKIE_NAME = "ddmp_visitor"
    SKIP_PREFIXES = ("/admin/", "/static/", "/media/", "/health/", "/q/", "/inquiries/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        visitor_id = request.COOKIES.get(self.COOKIE_NAME)
        try:
            uuid.UUID(visitor_id or "")
        except (ValueError, TypeError):
            visitor_id = str(uuid.uuid4())
            set_cookie = True
        else:
            set_cookie = False

        response = self.get_response(request)
        content_type = response.get("Content-Type", "")
        if (
            request.method == "GET"
            and response.status_code == 200
            and "text/html" in content_type
            and not request.path.startswith(self.SKIP_PREFIXES)
        ):
            try:
                VisitEvent.objects.create(
                    path=request.path[:300],
                    source_code=getattr(request, "campaign_source", "direct")[:40],
                    visitor_hash=hashlib.sha256(visitor_id.encode()).hexdigest(),
                )
            except DatabaseError:
                # Allows healthily starting the app before a newly deployed migration is applied.
                pass
        if set_cookie:
            response.set_cookie(
                self.COOKIE_NAME,
                visitor_id,
                max_age=365 * 24 * 3600,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure(),
            )
        return response
