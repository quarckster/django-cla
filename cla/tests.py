import json
from datetime import datetime
from datetime import timezone

import pytest
from django.conf import settings
from django.contrib.auth.models import User
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


def test_render_ccla_signing_request_form(client: Client):
    """
    Test that the CCLA signing request form renders correctly.
    """
    response = client.get(reverse("ccla"))
    assert response.status_code == 200
    assert b'<form action="submit/" method="post">' in response.content
    assert b'<input type="text" name="company" required id="id_company">' in response.content
    assert (
        b'<input type="text" name="authorized_signer_name" required id="id_authorized_signer_name">' in response.content
    )
    assert (
        b'<input type="email" name="authorized_signer_email" maxlength="320" required id="id_authorized_signer_email">'
        in response.content
    )
    assert b'<button type="submit">Send signing request</button>' in response.content


def test_render_icla_signing_request_form(client: Client):
    """
    Test that the ICLA signing request form renders correctly.
    """
    response = client.get(reverse("icla"))
    assert response.status_code == 200
    assert b'<form action="submit/" method="post">' in response.content
    assert b'<input type="email" name="email" maxlength="320" required id="id_email">' in response.content
    assert b'<button type="submit">Send signing request</button>' in response.content


@pytest.mark.django_db
def test_send_signing_request_ccla_new_email(mocker: MockerFixture, settings: settings, client: Client):
    """
    Test that a signing request is sent for a new email and no CCLA is created yet.
    """
    mock_create_submission = mocker.patch("cla.views.docuseal.create_submission")
    company = "Company"
    authorized_signer_name = "John Doe"
    authorized_signer_email = "john.doe@example.com"
    response = client.post(
        reverse("ccla-submit"),
        {
            "company": company,
            "authorized_signer_name": authorized_signer_name,
            "authorized_signer_email": authorized_signer_email,
        },
    )

    assert response.status_code == 200
    assert response.content == b"Signing request has been sent"
    mock_create_submission.assert_called_once_with(
        {
            "template_id": settings.DOCUSEAL_CCLA_TEMPLATE_ID,
            "send_email": True,
            "reply_to": "cla@openssl.org",
            "submitters": [
                {
                    "email": authorized_signer_email,
                    "role": "Authorized Signer",
                    "name": "John Doe",
                    "values": {"Corporation name": company},
                }
            ],
        }
    )
    assert CCLA.objects.count() == 0


@pytest.mark.django_db
def test_send_signing_request_icla_new_email(mocker: MockerFixture, settings: settings, client: Client):
    """
    Test that a signing request is sent for a new email and no ICLA is created yet.
    """
    mock_create_submission = mocker.patch("cla.views.docuseal.create_submission")
    email = "new_contributor@example.com"
    response = client.post(reverse("icla-submit"), {"email": email})

    assert response.status_code == 200
    assert response.content == b"Signing request has been sent"
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
    assert ICLA.objects.count() == 0


@pytest.mark.django_db
def test_send_signing_request_ccla_existing_ccla(mocker: MockerFixture, client: Client):
    """
    Test that a signing request is not sent if an CCLA for the email already exists.
    """
    mock_create_submission = mocker.patch("cla.views.docuseal.create_submission")
    authorized_signer_email = "john.doe@example.com"
    authorized_signer_name = "John Doe"
    company = "Company"
    user = User.objects.create(username="Jan Doe", first_name="Jane", last_name="Doe", email="jane.doe@example.org")
    CCLA.objects.create(
        authorized_signer_email=authorized_signer_email,
        authorized_signer_name=authorized_signer_name,
        authorized_signer_title="Title",
        corporation_address="123 Main St",
        corporation_name=company,
        docuseal_submission_id=123,
        fax="555-1234",
        point_of_contact=user,
        telephone="555-1234",
    )

    response = client.post(
        reverse("ccla-submit"),
        {
            "company": company,
            "authorized_signer_name": authorized_signer_name,
            "authorized_signer_email": authorized_signer_email,
        },
    )

    assert response.status_code == 200
    assert response.content == b"Signing request has been sent"
    mock_create_submission.assert_not_called()
    assert CCLA.objects.count() == 1


@pytest.mark.django_db
def test_send_signing_request_icla_existing_icla(mocker: MockerFixture, client: Client):
    """
    Test that a signing request is not sent if an ICLA for the email already exists.
    """
    mock_create_submission = mocker.patch("cla.views.docuseal.create_submission")
    mock_download_document = mocker.patch("cla.models.download_document")
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

    response = client.post(reverse("icla-submit"), {"email": email})

    assert response.status_code == 200
    assert response.content == b"Signing request has been sent"
    mock_create_submission.assert_not_called()
    assert ICLA.objects.count() == 1


@pytest.mark.django_db
def test_send_signing_request_ccla_invalid_form(client: Client):
    """
    Test that an invalid form submission returns a bad request response.
    """
    response = client.post(reverse("ccla-submit"), {"email": "invalid-email"})
    assert response.status_code == 400
    assert response.content == b"Submitted form is not valid"
    assert ICLA.objects.count() == 0


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
    assert ccla.point_of_contact.first_name == "Jane"
    assert ccla.point_of_contact.last_name == "Doe"
    assert ccla.point_of_contact.email == "jane.doe@example.org"
    assert ccla.point_of_contact.username == "jane.doe@example.org"
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
    mocker.patch("cla.models.download_document")
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

    response = client.post(reverse("webhooks-icla"), json.dumps(payload), content_type="application/json")

    assert response.status_code == 200
    assert response.content == b"ok"

    icla = ICLA.objects.get(email="test@example.com")
    assert icla.mailing_address == "123 Test St"
    assert icla.signed_at == FIXED_NOW
