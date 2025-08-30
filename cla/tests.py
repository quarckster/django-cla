import json
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
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


@pytest.fixture()
def setup_superuser():
    User = get_user_model()
    if not User.objects.filter(is_superuser=True).exists():
        User.objects.create_superuser("admin", "admin@example.com", "password123")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fields",
    [
        {"point_of_contact": "user@example.com", "in_schedule_a": True},
        {"point_of_contact": "user@example.com", "signed_at": FIXED_NOW},
        {},
    ],
    ids=["employee-not-signed", "employee-not-in-schedule-a", "volunteer-not-signed"],
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
        {"point_of_contact": "user@example.com", "in_schedule_a": True, "cla_pdf": "ICLA/some.pdf"},
        {"cla_pdf": "ICLA/some.pdf"},
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
@pytest.mark.usefixtures("setup_superuser")
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

    admin_login = client.login(username="admin", password="password123")
    assert admin_login, "Failed to login as admin for admin site test"

    icla_admin_url = reverse("admin:cla_icla_changelist")
    admin_response = client.get(icla_admin_url)
    assert admin_response.status_code == 200
    assert b"ICLA" in admin_response.content


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
                        {"field": "Public Name", "value": None},
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


@pytest.mark.django_db
def test_send_signing_request_icla_turnstile_fails(mocker: MockerFixture, client: Client):
    """
    Test that the signing request is rejected if Turnstile verification fails.
    """
    mock_verify_turnstile_token = mocker.patch("cla.views.verify_turnstile_token", return_value=False)
    email = "new_contributor@example.com"
    response = client.post(reverse("icla-submit"), {"email": email, "cf-turnstile-response": "token"})

    assert response.status_code == 400
    assert response.content == b"Turnstile token verification failed"
    mock_verify_turnstile_token.assert_called_once()
    assert not ICLA.objects.filter(email=email).exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_superuser")
def test_ccla_admin_page_loads_with_inlines(client: Client):
    """
    Test that the CCLA admin page and its inlines load successfully for a superuser.
    """
    User = get_user_model()
    manager = User.objects.create_user("manager", "manager@example.com", "password")
    ccla = CCLA.objects.create(
        corporation_name="Test Corp", ccla_manager=manager, authorized_signer_email="signer@example.com"
    )
    ICLA.objects.create(email="employee@testcorp.com", ccla=ccla)

    client.login(username="admin", password="password123")
    admin_url = reverse("admin:cla_ccla_change", args=(ccla.id,))
    response = client.get(admin_url)

    assert response.status_code == 200
    assert b"Test Corp" in response.content
    # Check for inline content
    assert b"employee@testcorp.com" in response.content
    assert b"CCLA Attachments" in response.content


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_superuser")
def test_pdf_views_require_login(client: Client):
    """
    Test that accessing PDF download views without being logged in redirects to the login page.
    """
    icla_url = reverse("media-icla-filename", args=("some.pdf",))
    ccla_url = reverse("media-ccla-directory-filename", args=("some_dir", "some.pdf"))

    icla_response = client.get(icla_url)
    ccla_response = client.get(ccla_url)

    assert icla_response.status_code == 302
    assert icla_response.url.startswith("/accounts/login/?next=/media/ICLA/some.pdf")
    assert ccla_response.status_code == 302
    assert ccla_response.url.startswith("/accounts/login/?next=/media/CCLA/some_dir/some.pdf")


@pytest.mark.django_db
@pytest.mark.usefixtures("setup_superuser")
def test_get_pdf_views_authenticated(client: Client, settings: settings):
    """
    Test that a logged-in user can successfully access the PDF files.
    """
    media_root = Path(settings.MEDIA_ROOT)
    icla_dir = media_root / "ICLA"
    icla_dir.mkdir(parents=True, exist_ok=True)
    (icla_dir / "test.pdf").write_text("ICLA content")

    ccla_dir = media_root / "CCLA" / "test_dir"
    ccla_dir.mkdir(parents=True, exist_ok=True)
    (ccla_dir / "test.pdf").write_text("CCLA content")

    client.login(username="admin", password="password123")

    # Test ICLA PDF view
    icla_url = reverse("media-icla-filename", args=("test.pdf",))
    icla_response = client.get(icla_url)
    assert icla_response.status_code == 200

    # Test CCLA PDF view
    ccla_url = reverse("media-ccla-directory-filename", args=("test_dir", "test.pdf"))
    ccla_response = client.get(ccla_url)
    assert ccla_response.status_code == 200


def test_cla_file_name_helper():
    """
    Test the cla_file_name helper function for correct path generation.
    """
    from cla.models import cla_file_name

    icla_id = uuid.uuid4()
    ccla_id = uuid.uuid4()

    # Mock model instances
    icla_instance = ICLA(id=icla_id)
    ccla_instance = CCLA(id=ccla_id)

    assert cla_file_name(icla_instance) == f"ICLA/{icla_id}.pdf"
    assert cla_file_name(ccla_instance) == f"CCLA/{ccla_id}/{ccla_id}.pdf"
