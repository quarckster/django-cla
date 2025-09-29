import logging

from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.views.decorators.http import require_safe

from cla.models import ICLA
from personnel.models import Group
from personnel.models import Person


logger = logging.getLogger(__name__)


@require_safe
def list_people(request: HttpRequest) -> HttpResponse:
    return JsonResponse(Person.list_people(), safe=False)


@require_safe
def find_person(request: HttpRequest, id: str) -> HttpResponse:
    if person := Person.find(id):
        return JsonResponse({"ids": person.ids, "tags": person.tags, "memberof": person.memberof}, safe=False)
    return HttpResponse(status=204)


@require_safe
def get_person_membership(request: HttpRequest, id: str) -> HttpResponse:
    if person := Person.find(id):
        return JsonResponse(person.memberof, safe=False)
    return HttpResponse(status=204)


@require_safe
def is_person_in_group(request: HttpRequest, id: str, group: str) -> HttpResponse:
    if (person := Person.find(id)) and group in person.memberof:
        return JsonResponse([person.memberof[group]], safe=False)
    return HttpResponse(status=204)


@require_safe
def get_person_tag(request: HttpRequest, id: str, tag: str) -> HttpResponse:
    if (person := Person.find(id)) and tag in person.tags:
        return JsonResponse([person.tags[tag]], safe=False)
    return HttpResponse(status=204)


@require_safe
def get_person_cla(request: HttpRequest, id: str) -> HttpResponse:
    if person := Person.find(id):
        return JsonResponse([icla.email for icla in person.iclas.all() if icla.is_active], safe=False)
    return HttpResponse(status=204)


@require_safe
def get_group_members(request: HttpRequest, group: str) -> HttpResponse:
    try:
        g = Group.objects.get(name=group)
        members = [person.ids for person in g.active_members]
        return JsonResponse(members, safe=False)
    except (Group.DoesNotExist, Group.MultipleObjectsReturned):
        return HttpResponse(status=204)


@require_safe
def get_group_members_cla(request: HttpRequest, group: str) -> HttpResponse:
    try:
        g = Group.objects.get(name=group)
        return JsonResponse(g.icla_emails, safe=False)
    except (Group.DoesNotExist, Group.MultipleObjectsReturned):
        return HttpResponse(status=204)


@require_safe
def get_email_cla(request: HttpRequest, email: str) -> HttpResponse:
    try:
        icla = ICLA.objects.get(email=email)
        if icla.is_active:
            return JsonResponse([1], safe=False)
    except ICLA.DoesNotExist:
        pass
    return HttpResponse(status=204)


@require_safe
def get_list_clas(request: HttpRequest) -> HttpResponse:
    iclas = [icla.email for icla in ICLA.objects.all() if icla.is_active]
    return JsonResponse(sorted(iclas), safe=False)
