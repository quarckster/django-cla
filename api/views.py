import json
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .cla_check import process
from .forms import ContactForm
from base.common import verify_turnstile_token

logger = logging.getLogger(__name__)


NULL_ACTIONS = (
    "assigned",
    "unassigned",
    "labeled",
    "unlabeled",
    "closed",
    "review_requested",
    "review_request_removed",
)


@require_POST
@csrf_exempt
def handle_github_pull_request_webhook(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body)
    if request.headers["X-GitHub-Event"] == "ping":
        return HttpResponse("pong")
    if request.headers["X-GitHub-Event"] != "pull_request":
        return HttpResponseBadRequest("Only pull_request event is supported.")
    if action := payload["action"] in NULL_ACTIONS:
        return HttpResponse(f"No-op action {action}")
    return process(payload["pull_request"])


@require_POST
@csrf_exempt
def send_message_from_contact_form(request: HttpRequest) -> HttpResponse:
    form = ContactForm(request.POST)
    if not form.is_valid():
        logger.warning("Submitted form is not valid: %s", form.errors.as_json())
        return HttpResponseBadRequest("Submitted form is not valid")
    if not request.POST.get("cf-turnstile-response"):
        logger.warning("Missing Turnstile token")
        return HttpResponseBadRequest("Missing Turnstile token")
    if not verify_turnstile_token(request):
        logger.warning("Turnstile token verification failed")
        return HttpResponseBadRequest("Turnstile token verification failed")
    email = form.cleaned_data["email"]
    name = form.cleaned_data["name"]
    message = form.cleaned_data["message"]
    message = f"Name: {name}\nEmail: {email}\nMessage: {message}"
    EmailMessage(
        subject="Contact form message",
        body=message,
        reply_to=[email],
        from_email=settings.NOTIFICATIONS_SENDER_EMAIL,
        to=[settings.CONTACT_FORM_RECIPIENTS],
    ).send()
    return HttpResponseRedirect(settings.CONTACT_FORM_SUBMISSION_SUCCESS_URL)
