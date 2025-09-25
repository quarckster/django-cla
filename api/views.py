import json
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_safe

from .cla_check import process
from .forms import ContactForm
from base.common import verify_turnstile_token
from cla.models import ICLA
from personnel.models import Group
from personnel.models import Person

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
        return "pong"
    if request.headers["X-GitHub-Event"] != "pull_request":
        return HttpResponseBadRequest("Only pull_request event is supported.")
    if action := payload["action"] in NULL_ACTIONS:
        return HttpResponse(f"No-op action {action}")
    process(payload["pull_request"])
    return HttpResponse("ok")


@require_POST
@csrf_exempt
def send_message_from_contact_form(request: HttpRequest) -> HttpResponse:
    logger.warning("request: %s", request.POST)
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


@require_safe
def list_people(request: HttpRequest) -> HttpResponse:
    return JsonResponse(Person.list_people(), safe=False)


@require_safe
def find_person(request: HttpRequest, id: str) -> HttpResponse:
    if person := Person.find(id):
        return JsonResponse({"ids": person.ids, "tags": person.tags, "memberof": person.memberof}, safe=False)
    return HttpResponse()


@require_safe
def get_person_membership(request: HttpRequest, id: str) -> HttpResponse:
    if person := Person.find(id):
        return JsonResponse(person.memberof, safe=False)
    return HttpResponse()


@require_safe
def is_person_in_group(request: HttpRequest, id: str, group: str) -> HttpResponse:
    if (person := Person.find(id)) and group in person.memberof:
        return JsonResponse([person.memberof[group]], safe=False)
    return HttpResponse()


@require_safe
def get_person_tag(request: HttpRequest, id: str, tag: str) -> HttpResponse:
    if (person := Person.find(id)) and tag in person.tags:
        return JsonResponse([person.tags[tag]], safe=False)
    return HttpResponse()


@require_safe
def get_person_cla(request: HttpRequest, id: str) -> HttpResponse:
    if person := Person.find(id):
        return JsonResponse([icla.email for icla in person.iclas.all() if icla.is_active], safe=False)
    return HttpResponse()


@require_safe
def get_group_members(request: HttpRequest, group: str) -> HttpResponse:
    try:
        g = Group.objects.get(name=group)
        members = [person.ids for person in g.members.all()]
        return JsonResponse(members, safe=False)
    except (Group.DoesNotExist, Group.MultipleObjectsReturned):
        return HttpResponse()


@require_safe
def get_group_members_cla(request: HttpRequest, group: str) -> HttpResponse:
    try:
        g = Group.objects.get(name=group)
        return JsonResponse(g.icla_emails, safe=False)
    except (Group.DoesNotExist, Group.MultipleObjectsReturned):
        return HttpResponse()


@require_safe
def get_email_cla(request: HttpRequest, email: str) -> HttpResponse:
    try:
        icla = ICLA.objects.get(email=email)
        if icla.is_active:
            return JsonResponse([1], safe=False)
    except ICLA.DoesNotExist:
        return HttpResponse()


@require_safe
def get_list_clas(request: HttpRequest) -> HttpResponse:
    iclas = [icla.email for icla in ICLA.objects.all() if icla.is_active]
    return JsonResponse(sorted(iclas), safe=False)
