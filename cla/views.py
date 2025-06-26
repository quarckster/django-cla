import json
import logging

from django import forms
from django.conf import settings
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_safe
from docuseal import docuseal

from .models import ICLA


logger = logging.getLogger(__name__)


class ICLASigningRequestForm(forms.Form):
    email = forms.EmailField(label="Email", required=True)


@require_POST
def send_signing_request_icla(request: HttpRequest) -> HttpResponse:
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
                "submitters": [{"email": email, "role": "Contributor"}],
            }
        )
    return HttpResponse(b"Siging request has been sent")


@require_safe
def render_icla_signing_request_form(request: HttpRequest) -> HttpResponse:
    form = ICLASigningRequestForm()
    return render(request, "cla/icla_sign_request.html", {"form": form})


@require_POST
@csrf_exempt
def handle_submission_completed_webhook(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body)
    submitter = payload["data"]["submitters"][0]

    def get_value_of(field: str) -> str | None:
        for field_value in submitter["values"]:
            if field == field_value["field"]:
                return field_value["value"]
        return None

    try:
        ICLA(
            country=get_value_of("Country"),
            docuseal_submission_id=payload["data"]["id"],
            email=get_value_of("Email"),
            full_name=get_value_of("Full Name"),
            mailing_address=f"{get_value_of('Mailing Address 1')}{get_value_of('Mailing Address 2')}",
            public_name=get_value_of("Public Name"),
            signed_at=submitter["completed_at"],
            telephone=get_value_of("Telephone"),
        ).save()
    except Exception:
        return HttpResponseBadRequest()
    return HttpResponse(b"ok")
