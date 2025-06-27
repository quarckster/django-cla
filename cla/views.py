import json
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_safe
from docuseal import docuseal

from .forms import CCLASigningRequestForm
from .forms import ICLASigningRequestForm
from .models import CCLA
from .models import ICLA


logger = logging.getLogger(__name__)


CCLA_EXPECTED_FIELDS = [
    "Corporation address 1",
    "Corporation address 2",
    "Corporation address 3",
    "Corporation name",
    "Email",
    "Fax",
    "Point of Contact",
    "Telephone",
]


ICLA_EXPECTED_FIELDS = [
    "Country",
    "Email",
    "Full Name",
    "Mailing Address 1",
    "Mailing Address 2",
    "Public Name",
    "Telephone",
]


@require_POST
def send_ccla_signing_request(request: HttpRequest) -> HttpResponse:
    form = CCLASigningRequestForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest(b"Submitted form is not valid")
    email = form.cleaned_data["authorized_signer_email"]
    name = form.cleaned_data["authorized_signer_name"]
    company = form.cleaned_data["company"]
    try:
        CCLA.objects.get(corporation_name=company)
    except CCLA.DoesNotExist:
        docuseal.key = settings.DOCUSEAL_KEY
        docuseal.create_submission(
            {
                "template_id": settings.DOCUSEAL_CCLA_TEMPLATE_ID,
                "send_email": True,
                "reply_to": settings.CLA_REPLY_TO_EMAIL,
                "submitters": [
                    {
                        "email": email,
                        "name": name,
                        "role": "Authorized Signer",
                        "values": {"Corporation name": company},
                    },
                ],
            }
        )
    return HttpResponse(b"Signing request has been sent")


@require_POST
def send_icla_signing_request(request: HttpRequest) -> HttpResponse:
    form = ICLASigningRequestForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest(b"Submitted form is not valid")
    email = form.cleaned_data["email"]
    try:
        ICLA.objects.get(email=email)
    except ICLA.DoesNotExist:
        docuseal.key = settings.DOCUSEAL_KEY
        docuseal.create_submission(
            {
                "template_id": settings.DOCUSEAL_ICLA_TEMPLATE_ID,
                "send_email": True,
                "reply_to": settings.CLA_REPLY_TO_EMAIL,
                "submitters": [{"email": email, "role": "Contributor", "values": {"Email": email}}],
            }
        )
    return HttpResponse(b"Signing request has been sent")


@require_safe
def render_ccla_signing_request_form(request: HttpRequest) -> HttpResponse:
    form = CCLASigningRequestForm()
    return render(request, "cla/ccla_signing_request.html", {"form": form})


@require_safe
def render_icla_signing_request_form(request: HttpRequest) -> HttpResponse:
    form = ICLASigningRequestForm()
    return render(request, "cla/icla_signing_request.html", {"form": form})


def make_submission_data_map(submitter_values: list[dict[str, str]]) -> dict[str, str]:
    result = {}
    for field_value in submitter_values:
        result[field_value["field"]] = field_value["value"]
    return result


@require_POST
@csrf_exempt
def handle_ccla_submission_completed_webhook(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body)
    submitter = payload["data"]["submitters"][0]
    submission_data = make_submission_data_map(submitter["values"])
    if diff := set(CCLA_EXPECTED_FIELDS).difference(submission_data.keys()):
        logger.error("Missing expected fields: %s", ", ".join(diff))
        return HttpResponseBadRequest()
    address_1 = submission_data["Corporation address 1"]
    address_2 = submission_data["Corporation address 2"]
    address_3 = submission_data["Corporation address 3"]
    poc_email = submission_data["Email"]
    poc_name = submission_data["Point of Contact"]
    poc_first_name = poc_name.split()[0]
    poc_last_name = " ".join(poc_name.split()[1:])
    user, _ = User.objects.get_or_create(
        username=poc_email, first_name=poc_first_name, last_name=poc_last_name, email=poc_email
    )
    try:
        CCLA(
            authorized_signer_email=submitter["email"],
            authorized_signer_name=submitter["name"],
            authorized_signer_title=submission_data["Title"],
            corporation_address=address_1 + address_2 + address_3,
            corporation_name=submission_data["Corporation name"],
            docuseal_submission_id=payload["data"]["id"],
            fax=submission_data["Fax"],
            point_of_contact=user,
            signed_at=submitter["completed_at"],
            telephone=submission_data["Telephone"],
        ).save()
    except Exception as e:
        logger.exception(e)
        return HttpResponseBadRequest()
    return HttpResponse(b"ok")


@require_POST
@csrf_exempt
def handle_icla_submission_completed_webhook(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body)
    submitter = payload["data"]["submitters"][0]
    submission_data = make_submission_data_map(submitter["values"])
    if diff := set(ICLA_EXPECTED_FIELDS).difference(submission_data.keys()):
        logger.error("Missing expected fields: %s", ", ".join(diff))
        return HttpResponseBadRequest()
    try:
        ICLA(
            country=submission_data["Country"],
            docuseal_submission_id=payload["data"]["id"],
            email=submission_data["Email"],
            full_name=submission_data["Full Name"],
            mailing_address=submission_data["Mailing Address 1"] + submission_data["Mailing Address 2"],
            public_name=submission_data["Public Name"],
            signed_at=submitter["completed_at"],
            telephone=submission_data["Telephone"],
        ).save()
    except Exception as e:
        logger.exception(e)
        return HttpResponseBadRequest()
    return HttpResponse(b"ok")
