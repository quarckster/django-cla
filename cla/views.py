import json
import logging

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_safe

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


@ensure_csrf_cookie
@require_safe
def get_csrf_token(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"csrfToken": get_token(request)})


def verify_turnstile_token(request: HttpRequest) -> bool:
    logger.info("Verify Turnstile token")
    resp = requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={
            "secret": settings.CLOUDFLARE_TURNSTILE_SECRET_KEY,
            "response": request.POST.get("cf-turnstile-response"),
            "remoteip": request.META.get("CF-Connecting-IP"),
        },
        timeout=5,
    )
    result = resp.json()
    return bool(result.get("success"))


@require_POST
def send_icla_signing_request(request: HttpRequest) -> HttpResponse:
    form = ICLASigningRequestForm(request.POST)
    if not form.is_valid():
        logger.warning("Submitted form is not valid")
        return HttpResponseBadRequest("Submitted form is not valid")
    if not request.POST.get("cf-turnstile-response"):
        logger.warning("Missing Turnstile token")
        return HttpResponseBadRequest("Missing Turnstile token")
    if not verify_turnstile_token(request):
        logger.warning("Turnstile token verification failed")
        return HttpResponseBadRequest("Turnstile token verification failed")
    email = form.cleaned_data["email"]
    point_of_contact = form.cleaned_data["point_of_contact"]
    try:
        ICLA.objects.get(email=email)
    except ICLA.DoesNotExist:
        icla = ICLA(email=email, point_of_contact=point_of_contact)
        icla.save()
        icla.create_docuseal_submission()
    else:
        logger.warning("%s has already signed ICLA", email)
    return HttpResponse("Signing request has been sent")


def make_submission_data_map(submitter_values: list[dict[str, str]]) -> dict[str, str]:
    result = {}
    for field_value in submitter_values:
        result[field_value["field"]] = field_value["value"]
    return result


@require_POST
@csrf_exempt
@transaction.atomic
def handle_ccla_submission_completed_webhook(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body)
    submitter = payload["data"]["submitters"][0]
    submission_data = make_submission_data_map(submitter["values"])
    if diff := set(CCLA_EXPECTED_FIELDS).difference(submission_data.keys()):
        msg = "Missing expected fields: %s", ", ".join(diff)
        logger.error(msg)
        return HttpResponseBadRequest(msg)
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
    CCLA(
        authorized_signer_email=submitter["email"],
        authorized_signer_name=submitter["name"],
        authorized_signer_title=submission_data["Title"],
        corporation_address=address_1 + address_2 + address_3,
        corporation_name=submission_data["Corporation name"],
        docuseal_submission_id=payload["data"]["id"],
        fax=submission_data["Fax"],
        ccla_manager=user,
        signed_at=submitter["completed_at"],
        telephone=submission_data["Telephone"],
    ).save()
    return HttpResponse("ok")


@require_POST
@csrf_exempt
def handle_icla_submission_completed_webhook(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body)
    submitter = payload["data"]["submitters"][0]
    submission_data = make_submission_data_map(submitter["values"])
    if diff := set(ICLA_EXPECTED_FIELDS).difference(submission_data.keys()):
        msg = "Missing expected fields: %s", ", ".join(diff)
        logger.error(msg)
        return HttpResponseBadRequest(msg)
    icla = ICLA.objects.get(email=submission_data["Email"])
    icla.country = submission_data["Country"]
    icla.docuseal_submission_id = payload["data"]["id"]
    icla.email = submission_data["Email"]
    icla.full_name = submission_data["Full Name"]
    icla.mailing_address = submission_data["Mailing Address 1"] + submission_data["Mailing Address 2"]
    icla.public_name = submission_data["Public Name"]
    icla.signed_at = submitter["completed_at"]
    icla.telephone = submission_data["Telephone"]
    icla.save()
    return HttpResponse("ok")
