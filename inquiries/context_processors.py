import uuid

from .models import RegionalContact


def contact_service(request):
    saved_values = request.session.pop("inquiry_form_values", {})
    return {
        "regional_contacts": RegionalContact.published.all(),
        "inquiry_submission_key": str(uuid.uuid4()),
        "campaign_source": getattr(request, "campaign_source", "direct"),
        "inquiry_form_values": saved_values,
    }
