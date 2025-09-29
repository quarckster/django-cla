import json
from datetime import date
from datetime import timedelta
from typing import Any
from datetime import datetime
from datetime import timezone

import pytest
from django.test import Client
from django.urls import reverse
from pytest_mock import MockerFixture

from cla.models import ICLA
from personnel.models import Email
from personnel.models import Group
from personnel.models import Identity
from personnel.models import Membership
from personnel.models import Person


def make_person(
    *,
    name: str = "Alice",
    country: str | None = "CZ",
    nick: str | None = "ali",
    github: str | None = "alice-gh",
    ghe: str | None = "alice-ghe",
    rev: str | None = "alice-rev",
    emails: list[str] | None = None,
    identities: list[str] | None = None,
) -> Person:
    p = Person.objects.create(
        name=name,
        country=country or "",
        nick=nick or "",
        github=github,
        ghe=ghe,
        rev=rev,
    )
    for e in emails or [f"{name.lower()}@example.org"]:
        Email.objects.create(person=p, email=e)
    for i in identities or [f"{name.lower()}-id"]:
        Identity.objects.create(person=p, identity=i)
    return p


def add_membership(person: Person, group: Group, *, since: date | None, until: date | None):
    Membership.objects.create(person=person, group=group, since=since, until=until)



@pytest.mark.django_db
def test_person_tags_only_includes_nonempty_fields():
    p = make_person(country="CZ", rev="rev-123", github=None, ghe=None)
    # no PGP set, ensure it's not included
    tags = p.tags
    assert tags == {"country": "CZ", "rev": "rev-123"}


@pytest.mark.django_db
def test_person_ids_aggregation_and_ordering():
    p = make_person(
        name="Bob",
        nick="b",
        github="bobgh",
        ghe="bobghe",
        emails=["bob@example.org", "bob@alt.example.org"],
        identities=["bob-id", "bob-id2"],
    )
    ids = p.ids
    # must contain emails and identities (de-duplicated), then name, then dict-based ids
    assert "bob@example.org" in ids and "bob-id" in ids
    assert "Bob" in ids
    assert {"nick": "b"} in ids and {"ghe": "bobghe"} in ids and {"github": "bobgh"} in ids


@pytest.mark.django_db
def test_person_memberof_and_group_active_members():
    today = date.today()
    g = Group.objects.create(name="dev")
    p_active = make_person(name="Carol", ghe=None, github=None, rev=None)
    p_inactive = make_person(name="Dave", ghe=None, github=None, rev=None)
    add_membership(p_active, g, since=today - timedelta(days=30), until=None)
    add_membership(p_inactive, g, since=today - timedelta(days=90), until=today - timedelta(days=1))

    # memberof property
    assert "dev" in p_active.memberof
    assert "dev" not in p_inactive.memberof

    assert list(g.active_members) == [p_active]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "needle,expected",
    [
        # name
        ("Eve", True),
        # nick
        ("eve-nick", True),
        # ghe
        ("eve-ghe", True),
        # github
        ("eve-gh", True),
        # email
        ("eve@example.org", True),
        # identity
        ("eve-id", True),
        ("nonexistent", False),
    ],
)
def test_person_find_various_identifiers(needle: str, expected: bool):
    p = make_person(
        name="Eve",
        nick="eve-nick",
        ghe="eve-ghe",
        github="eve-gh",
        emails=["eve@example.org"],
        identities=["eve-id"],
    )
    found = Person.find(needle)
    if expected:
        assert found == p
    else:
        assert found is None


@pytest.mark.django_db
def test_list_people_returns_all_ids(client: Client):
    a = make_person(name="Anna", nick="an", ghe=None, github=None, rev=None)
    b = make_person(name="Ben", nick="bn", ghe=None, github=None, rev=None)
    response = client.get(reverse("0-people"))
    assert response.status_code == 200
    payload = json.loads(response.content)
    assert a.ids in payload
    assert b.ids in payload


@pytest.mark.django_db
def test_list_people_uses_model_method_mocked(mocker: MockerFixture, client: Client):
    mocker.patch.object(Person, "list_people", return_value=[["stub@example.org", "Stub"]])
    response = client.get(reverse("0-people"))
    assert response.status_code == 200
    assert json.loads(response.content) == [["stub@example.org", "Stub"]]


@pytest.mark.django_db
def test_find_person_endpoint_success(client: Client):
    p = make_person(name="Greg", nick="gr")
    response = client.get(reverse("0-person-id", args=("Greg",)))
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["ids"] == p.ids
    assert data["tags"] == p.tags
    assert data["memberof"] == p.memberof


@pytest.mark.django_db
def test_find_person_endpoint_not_found_returns_empty_body(client: Client):
    response = client.get(reverse("0-person-id", args=("nobody",)))
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.django_db
def test_get_person_membership(client: Client):
    today = date.today()
    g = Group.objects.create(name="ops")
    p = make_person(name="Helen")
    add_membership(p, g, since=today - timedelta(days=10), until=None)
    resp = client.get(reverse("0-person-id-membership", args=("Helen",)))
    assert resp.status_code == 200
    assert json.loads(resp.content) == p.memberof


@pytest.mark.django_db
def test_is_person_in_group_yes_and_no(client: Client):
    today = date.today()
    g = Group.objects.create(name="qa")
    p = make_person(name="Ivan")
    add_membership(p, g, since=today - timedelta(days=1), until=None)

    yes_resp = client.get(reverse("0-person-id-ismemberof-group", args=("Ivan", "qa")))
    assert yes_resp.status_code == 200
    assert json.loads(yes_resp.content) == [p.memberof["qa"]]

    no_resp = client.get(reverse("0-person-id-ismemberof-group", args=("Ivan", "dev")))
    assert no_resp.status_code == 204
    assert no_resp.content == b""


@pytest.mark.django_db
def test_get_person_tag_present_and_missing(client: Client):
    make_person(name="Jack", country="DE")
    has_tag = client.get(reverse("0-person-id-valueoftag-tag", args=("Jack", "country")))
    assert has_tag.status_code == 200
    assert json.loads(has_tag.content) == ["DE"]

    missing_tag = client.get(reverse("0-person-id-valueoftag-tag", args=("Jack", "pgp")))
    assert missing_tag.status_code == 204
    assert missing_tag.content == b""


@pytest.mark.django_db
def test_get_person_cla_returns_active_emails(client: Client):
    p = make_person(name="Kate", emails=["kate@example.org"])
    # Ensure ICLA is associated with the person and considered active.
    ICLA.objects.create(email="kate@example.org", person=p, cla_pdf="ICLA/kate.pdf")
    ICLA.objects.create(email="kate2@example.org", person=p, cla_pdf="ICLA/kate2.pdf")
    # Add an unrelated ICLA
    ICLA.objects.create(email="other@example.org", cla_pdf="ICLA/other.pdf")

    resp = client.get(reverse("0-person-id-hascla", args=("Kate",)))
    assert resp.status_code == 200
    data = json.loads(resp.content)
    assert set(data) == {"kate@example.org", "kate2@example.org"}


@pytest.mark.django_db
def test_get_person_cla_person_not_found_is_empty(client: Client):
    resp = client.get(reverse("0-person-id-hascla", args=("Ghost",)))
    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.django_db
def test_get_group_members_only_active(client: Client):
    today = date.today()
    g = Group.objects.create(name="security")
    a = make_person(name="AliceSec", nick="as", ghe=None, github=None, rev=None)
    b = make_person(name="BobSec", nick="bs", ghe=None, github=None, rev=None)
    c = make_person(name="CharlieOld", nick="co", ghe=None, github=None, rev=None)

    # active
    add_membership(a, g, since=today - timedelta(days=5), until=None)
    # active (since is null)
    add_membership(b, g, since=None, until=None)
    # inactive
    add_membership(c, g, since=today - timedelta(days=100), until=today - timedelta(days=1))

    resp = client.get(reverse("0-group-group-members", args=("security",)))
    assert resp.status_code == 200
    data = json.loads(resp.content)

    assert a.ids in data and b.ids in data
    assert all(ids != c.ids for ids in data)


@pytest.mark.django_db
def test_get_group_members_group_not_found_returns_empty(client: Client):
    resp = client.get(reverse("0-group-group-members", args=("nope",)))
    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.django_db
def test_get_group_members_cla_collects_icla_emails_from_active_members(client: Client):
    today = date.today()
    g = Group.objects.create(name="eng")
    a = make_person(name="Ann", emails=["ann@example.org"], ghe=None, github=None, rev=None)
    b = make_person(name="Ben", emails=["ben@example.org"], ghe=None, github=None, rev=None)
    z = make_person(name="Zoe", emails=["zoe@example.org"], ghe=None, github=None, rev=None)

    add_membership(a, g, since=today - timedelta(days=3), until=None)
    add_membership(b, g, since=today - timedelta(days=60), until=None)
    add_membership(z, g, since=today - timedelta(days=120), until=today - timedelta(days=1))

    ICLA.objects.create(email="ann@example.org", person=a, cla_pdf="ICLA/ann.pdf")
    ICLA.objects.create(email="ben@example.org", person=b, cla_pdf="ICLA/ben.pdf")
    ICLA.objects.create(email="zoe@example.org", person=z)

    resp = client.get(reverse("0-group-group-clas", args=("eng",)))
    assert resp.status_code == 200
    emails = set(json.loads(resp.content))
    assert emails == {"ann@example.org", "ben@example.org"}


@pytest.mark.django_db
def test_get_group_members_cla_group_not_found_returns_empty(client: Client):
    resp = client.get(reverse("0-group-group-clas", args=("missing",)))
    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.django_db
def test_get_list_clas_returns_sorted_active_emails(client: Client):
    ICLA.objects.create(email="b@example.org", cla_pdf="ICLA/b.pdf")
    ICLA.objects.create(email="a@example.org", cla_pdf="ICLA/a.pdf")
    ICLA.objects.create(email="x@example.org")

    resp = client.get(reverse("0-clas"))
    assert resp.status_code == 200
    assert json.loads(resp.content) == ["a@example.org", "b@example.org"]



FIXED_NOW = datetime(2025, 6, 25, 13, 45, 31, 892000, tzinfo=timezone.utc)

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
    response = client.get(reverse("0-hascla-email", args=(email,)))
    assert response.status_code == 204
    assert response.content == b""
