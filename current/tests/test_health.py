import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_check_returns_minimal_success_response(client):
    response = client.get(reverse("core:health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response["Cache-Control"] == "max-age=0, no-cache, no-store, must-revalidate, private"
