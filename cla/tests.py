import json
from datetime import datetime
from datetime import timezone
from unittest import mock

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from cla.models import ICLA


FIXED_NOW = datetime(2025, 6, 25, 13, 45, 31, 892000, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def set_settings(settings: settings):
    settings.DOCUSEAL_KEY = "test_docuseal_key"
    settings.DOCUSEAL_ICLA_TEMPLATE_ID = "test_template_id"
    settings.ICLA_WEBHOOK_SECRET_SLUG = "test_secret_slug"


@pytest.fixture
def webhook_url(settings: settings):
    return reverse(f"webhooks-icla")


def test_render_icla_signing_request_form(client: Client):
    """
    Test that the ICLA signing request form renders correctly.
    """
    response = client.get(reverse("icla"))
    assert response.status_code == 200
    assert b'<form action="submit/" method="post">' in response.content
    assert b'<input type="email" name="email" maxlength="320" required id="id_email">' in response.content
    assert b'<button type="submit">Send signing request</button>' in response.content


@mock.patch("cla.views.docuseal.create_submission")
@pytest.mark.django_db
def test_send_signing_request_icla_new_email(mock_create_submission, settings: settings, client: Client):
    """
    Test that a signing request is sent for a new email and no ICLA is created yet.
    """
    email = "new_contributor@example.com"
    response = client.post(reverse("icla-submit"), {"email": email})

    assert response.status_code == 200
    assert response.content == b"Siging request has been sent"
    mock_create_submission.assert_called_once_with(
        {
            "template_id": settings.DOCUSEAL_ICLA_TEMPLATE_ID,
            "send_email": True,
            "submitters": [{"email": email, "role": "Contributor"}],
        }
    )
    assert ICLA.objects.count() == 0


@mock.patch("cla.views.docuseal.create_submission")
@pytest.mark.django_db
def test_send_signing_request_icla_existing_icla(mock_create_submission, client: Client):
    """
    Test that a signing request is not sent if an ICLA for the email already exists.
    """
    email = "existing_contributor@example.com"
    ICLA.objects.create(
        email=email,
        full_name="Existing User",
        country="USA",
        docuseal_submission_id=123,
        mailing_address="123 Main St",
        public_name="Existing",
        telephone="555-1234",
    )

    response = client.post(reverse("icla-submit"), {"email": email})

    assert response.status_code == 200
    assert response.content == b"Siging request has been sent"
    mock_create_submission.assert_not_called()
    assert ICLA.objects.count() == 1


@pytest.mark.django_db
def test_send_signing_request_icla_invalid_form(client: Client):
    """
    Test that an invalid form submission returns a bad request response.
    """
    response = client.post(reverse("icla-submit"), {"email": "invalid-email"})
    assert response.status_code == 400
    assert response.content == b"Submitted form is not valid"
    assert ICLA.objects.count() == 0


@pytest.mark.django_db
def test_handle_submission_completed_webhook_success(client: Client, webhook_url: str):
    """
    Test that a valid webhook payload successfully creates an ICLA object.
    """
    payload = {
        "event_type": "submission.completed",
        "timestamp": "2025-06-25T13:45:33.140Z",
        "data": {
            "id": 2339638,
            "submitters": [
                {
                    "email": "dmitry@openssl.org",
                    "completed_at": "2025-06-25T13:45:31.892Z",
                    "values": [
                        {"field": "Full Name", "value": "Dmitry Misharov"},
                        {"field": "Public Name", "value": "Dmitry M."},
                        {"field": "Mailing Address 1", "value": "Brno, Kohoutovicka 203/72"},
                        {"field": "Mailing Address 2", "value": ""},
                        {"field": "Country", "value": "Czech Republic"},
                        {"field": "Telephone", "value": "123-456-7890"},
                        {"field": "Email", "value": "dmitry@openssl.org"},
                    ],
                }
            ],
        },
    }

    response = client.post(webhook_url, json.dumps(payload), content_type="application/json")

    assert response.status_code == 200
    assert response.content == b"ok"

    icla = ICLA.objects.get(email="dmitry@openssl.org")
    assert icla.docuseal_submission_id == 2339638
    assert icla.full_name == "Dmitry Misharov"
    assert icla.public_name == "Dmitry M."
    assert icla.mailing_address == "Brno, Kohoutovicka 203/72"
    assert icla.country == "Czech Republic"
    assert icla.telephone == "123-456-7890"
    assert icla.signed_at == FIXED_NOW


@pytest.mark.django_db(transaction=True)
def test_handle_submission_completed_webhook_missing_fields(client: Client, webhook_url: str):
    """
    Test that a webhook payload with missing mandatory fields results in a server error.
    """
    payload = {
        "event_type": "submission.completed",
        "timestamp": "2025-06-25T13:45:33.140Z",
        "data": {
            "id": 2339639,
            "submitters": [
                {
                    "email": "another@openssl.org",
                    "completed_at": "2025-06-25T13:45:31.892Z",
                    "values": [
                        {"field": "Full Name", "value": "Another User"},
                    ],
                }
            ],
        },
    }

    response = client.post(webhook_url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert ICLA.objects.count() == 0


@pytest.mark.django_db
def test_handle_submission_completed_webhook_empty_mailing_address2(client: Client, webhook_url: str):
    """
    Test that a valid webhook payload with an empty Mailing Address 2 creates an ICLA object correctly.
    """
    payload = {
        "event_type": "submission.completed",
        "timestamp": "2025-06-25T13:45:33.140Z",
        "data": {
            "id": 2339640,
            "submitters": [
                {
                    "email": "test@example.com",
                    "completed_at": "2025-06-25T13:45:31.892Z",
                    "values": [
                        {"field": "Full Name", "value": "Test User"},
                        {"field": "Public Name", "value": ""},
                        {"field": "Mailing Address 1", "value": "123 Test St"},
                        {"field": "Mailing Address 2", "value": ""},
                        {"field": "Country", "value": "USA"},
                        {"field": "Telephone", "value": ""},
                        {"field": "Email", "value": "test@example.com"},
                    ],
                }
            ],
        },
    }

    response = client.post(webhook_url, json.dumps(payload), content_type="application/json")

    assert response.status_code == 200
    assert response.content == b"ok"

    icla = ICLA.objects.get(email="test@example.com")
    assert icla.mailing_address == "123 Test St"
    assert icla.signed_at == FIXED_NOW
