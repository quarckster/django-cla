import json
from datetime import datetime
from datetime import timezone
from typing import Any

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse
from pytest_mock import MockerFixture

from cla.models import CCLA
from cla.models import ICLA


FIXED_NOW = datetime(2025, 6, 25, 13, 45, 31, 892000, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def set_settings(settings: settings):
    settings.DOCUSEAL_KEY = "test_docuseal_key"
    settings.DOCUSEAL_ICLA_TEMPLATE_ID = "123456"
    settings.DOCUSEAL_CCLA_TEMPLATE_ID = "123457"
    settings.ICLA_WEBHOOK_SECRET_SLUG = "test_secret_slug"
    settings.CCLA_WEBHOOK_SECRET_SLUG = "test_secret_slug"
    settings.ICLA_SUBMISSION_SUCCESS_URL = "https://example.com/success/"


def test_get_csrf_token(client: Client):
    response = client.get(reverse("csrf"))
    assert response.status_code == 200
    assert response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fields",
    [
        {"point_of_contact": "user@example.com", "employer_approved_at": FIXED_NOW},
        {"point_of_contact": "user@example.com", "signed_at": FIXED_NOW},
        {},
    ],
    ids=["employee-not-signed", "employee-not-approved", "volunteer-not-signed"],
)
def test_get_icla_status_not_active(client: Client, fields: dict[str, Any]):
    email = "test@example.com"
    ICLA.objects.create(email=email, **fields)
    response = client.get(reverse("icla-email-status", args=(email,)))
    assert response.status_code == 200
    assert json.loads(response.content) == {"email": email, "active": False}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fields",
    [
        {"point_of_contact": "user@example.com", "employer_approved_at": FIXED_NOW, "signed_at": FIXED_NOW},
        {"signed_at": FIXED_NOW},
    ],
    ids=["employee", "volunteer"],
)
def test_get_icla_status_active(client: Client, fields: dict[str, Any]):
    email = "test@example.com"
    ICLA.objects.create(email=email, **fields)
    response = client.get(reverse("icla-email-status", args=(email,)))
    assert response.status_code == 200
    assert json.loads(response.content) == {"email": email, "active": True}


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [{"point_of_contact": "user@example.com"}, {}], ids=["with-poc", "without-poc"])
def test_send_signing_request_icla_new_email(
    mocker: MockerFixture, settings: settings, client: Client, payload: dict[str, str]
):
    """
    Test that a signing request is sent for a new email and no ICLA is created yet.
    """
    mock_create_submission = mocker.patch("cla.models.docuseal.create_submission")
    mock_verify_turnstile_token = mocker.patch("cla.views.verify_turnstile_token", return_value=True)
    mock_send_mail = mocker.patch("cla.models.send_mail")
    mock_download_document = mocker.patch("cla.models.download_document")
    email = "new_contributor@example.com"
    response = client.post(reverse("icla-submit"), {"email": email, "cf-turnstile-response": "token", **payload})

    assert response.status_code == 302
    assert response.url == settings.ICLA_SUBMISSION_SUCCESS_URL
    mock_verify_turnstile_token.assert_called_once()
    mock_create_submission.assert_called_once_with(
        {
            "template_id": settings.DOCUSEAL_ICLA_TEMPLATE_ID,
            "send_email": True,
            "reply_to": "cla@openssl.org",
            "submitters": [
                {
                    "email": "new_contributor@example.com",
                    "role": "Contributor",
                    "values": {"Email": "new_contributor@example.com"},
                }
            ],
        }
    )
    mock_send_mail.assert_not_called()
    mock_download_document.assert_not_called()
    assert ICLA.objects.get(email=email).point_of_contact == payload.get("point_of_contact", "")


@pytest.mark.django_db
def test_send_signing_request_icla_missing_turnstile_token(client: Client):
    email = "new_contributor@example.com"
    response = client.post(reverse("icla-submit"), {"email": email})
    assert response.status_code == 400
    assert response.content == b"Missing Turnstile token"
    with pytest.raises(ICLA.DoesNotExist):
        ICLA.objects.get(email=email)


@pytest.mark.django_db
def test_send_signing_request_icla_existing_icla(mocker: MockerFixture, client: Client):
    """
    Test that a signing request is not sent if an ICLA for the email already exists.
    """
    mock_create_submission = mocker.patch("cla.models.docuseal.create_submission")
    mock_download_document = mocker.patch("cla.models.download_document")
    mock_verify_turnstile_token = mocker.patch("cla.views.verify_turnstile_token", return_value=True)
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
    mock_download_document.assert_called_once()

    response = client.post(reverse("icla-submit"), {"email": email, "cf-turnstile-response": "token"})

    assert response.status_code == 302
    assert response.url == settings.ICLA_SUBMISSION_SUCCESS_URL
    mock_verify_turnstile_token.assert_called_once()
    mock_create_submission.assert_not_called()
    assert ICLA.objects.count() == 1


@pytest.mark.django_db
def test_send_signing_request_icla_invalid_email(client: Client):
    """
    Test that an invalid form submission returns a bad request response.
    """
    response = client.post(reverse("icla-submit"), {"email": "invalid-email"})
    assert response.status_code == 400
    assert response.content == b"Submitted form is not valid"
    assert ICLA.objects.count() == 0


@pytest.mark.django_db
def test_handle_ccla_submission_completed_webhook_success(client: Client):
    """
    Test that a valid webhook payload successfully creates an CCLA object.
    """
    payload = {
        "event_type": "submission.completed",
        "timestamp": "2025-06-25T13:45:33.140Z",
        "data": {
            "id": 2339638,
            "submitters": [
                {
                    "email": "john.doe@example.com",
                    "name": "John Doe",
                    "completed_at": "2025-06-25T13:45:31.892Z",
                    "values": [
                        {"field": "Corporation address 1", "value": "Some address"},
                        {"field": "Corporation address 2", "value": ""},
                        {"field": "Corporation address 3", "value": ""},
                        {"field": "Corporation name", "value": "Company"},
                        {"field": "Email", "value": "jane.doe@example.org"},
                        {"field": "Fax", "value": "123-456-7891"},
                        {"field": "Point of Contact", "value": "Jane Doe"},
                        {"field": "Title", "value": "President"},
                        {"field": "Telephone", "value": "123-456-7890"},
                    ],
                }
            ],
        },
    }

    response = client.post(reverse("webhooks-ccla"), json.dumps(payload), content_type="application/json")

    assert response.status_code == 200
    assert response.content == b"ok"

    ccla = CCLA.objects.get(corporation_name="Company")
    assert ccla.authorized_signer_email == "john.doe@example.com"
    assert ccla.authorized_signer_name == "John Doe"
    assert ccla.authorized_signer_title == "President"
    assert ccla.corporation_address == "Some address"
    assert ccla.corporation_name == "Company"
    assert ccla.docuseal_submission_id == 2339638
    assert ccla.fax == "123-456-7891"
    assert ccla.ccla_manager.first_name == "Jane"
    assert ccla.ccla_manager.last_name == "Doe"
    assert ccla.ccla_manager.email == "jane.doe@example.org"
    assert ccla.ccla_manager.username == "jane.doe@example.org"
    assert ccla.signed_at == FIXED_NOW
    assert ccla.telephone == "123-456-7890"


@pytest.mark.django_db(transaction=True)
def test_handle_icla_submission_completed_webhook_missing_fields(client: Client):
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
                    "email": "another@example.com",
                    "completed_at": "2025-06-25T13:45:31.892Z",
                    "values": [
                        {"field": "Full Name", "value": "Another User"},
                    ],
                }
            ],
        },
    }

    response = client.post(reverse("webhooks-icla"), json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert ICLA.objects.count() == 0


@pytest.mark.django_db
def test_handle_icla_submission_completed_webhook_empty_mailing_address2(mocker: MockerFixture, client: Client):
    """
    Test that a valid webhook payload with an empty Mailing Address 2 creates an ICLA object correctly.
    """
    mock_download_document = mocker.patch("cla.models.download_document")
    email = "test@example.com"
    ICLA.objects.create(email=email)

    payload = {
        "event_type": "submission.completed",
        "timestamp": "2025-06-25T13:45:33.140Z",
        "data": {
            "id": 2339640,
            "submitters": [
                {
                    "email": email,
                    "completed_at": "2025-06-25T13:45:31.892Z",
                    "values": [
                        {"field": "Full Name", "value": "Test User"},
                        {"field": "Public Name", "value": ""},
                        {"field": "Mailing Address 1", "value": "123 Test St"},
                        {"field": "Mailing Address 2", "value": ""},
                        {"field": "Country", "value": "USA"},
                        {"field": "Telephone", "value": ""},
                        {"field": "Email", "value": email},
                    ],
                }
            ],
        },
    }

    response = client.post(reverse("webhooks-icla"), json.dumps(payload), content_type="application/json")
    mock_download_document.assert_called_once()

    assert response.status_code == 200
    assert response.content == b"ok"

    icla = ICLA.objects.get(email=email)
    assert icla.email == email
    assert icla.full_name == "Test User"
    assert icla.public_name == ""
    assert icla.telephone == ""
    assert icla.mailing_address == "123 Test St"
    assert icla.signed_at == FIXED_NOW
    assert icla.country == "USA"


@pytest.mark.django_db
def test_send_notification_called_only_via_icla_webhook(mocker: MockerFixture, client: Client):
    """
    send_notification() should be invoked exactly once when the webhook handler
    processes a completed ICLA submission.
    """

    mocker.patch("cla.models.download_document")
    mock_notify = mocker.patch.object(ICLA, "send_notification")

    email = "notify@example.com"
    ICLA.objects.create(email=email)

    payload = {
        "event_type": "submission.completed",
        "timestamp": FIXED_NOW.isoformat(),
        "data": {
            "id": 999,
            "submitters": [
                {
                    "email": email,
                    "completed_at": FIXED_NOW.isoformat(),
                    "values": [
                        {"field": "Full Name", "value": "Notify User"},
                        {"field": "Public Name", "value": ""},
                        {"field": "Mailing Address 1", "value": "1 Test Rd"},
                        {"field": "Mailing Address 2", "value": ""},
                        {"field": "Country", "value": "Testland"},
                        {"field": "Telephone", "value": "000"},
                        {"field": "Email", "value": email},
                    ],
                }
            ],
        },
    }

    response = client.post(reverse("webhooks-icla"), json.dumps(payload), content_type="application/json")
    assert response.status_code == 200
    mock_notify.assert_called_once()


@pytest.mark.django_db
def test_model_save_does_not_trigger_send_notification(mocker: MockerFixture, client: Client):
    """
    Plain .save() on the ICLA model (e.g. in the admin) must never call send_notification().
    """
    mock_notify = mocker.patch.object(ICLA, "send_notification")

    icla = ICLA.objects.create(email="adminsave@example.com")
    icla.full_name = "Admin Saved"
    icla.employer_approved_at = FIXED_NOW
    icla.signed_at = FIXED_NOW
    icla.save()

    mock_notify.assert_not_called()
