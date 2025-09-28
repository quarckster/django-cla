from __future__ import annotations

import uuid
from itertools import chain

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)

    @property
    def active_members(self) -> list[Person]:
        today = timezone.now().date()
        return self.members.filter(
            Q(membership__since__isnull=True) | Q(membership__since__lte=today),
            Q(membership__until__isnull=True) | Q(membership__until__gt=today),
        ).distinct()

    @property
    def icla_emails(self) -> list[str]:
        result = []
        members = [person for person in self.active_members]
        for member in members:
            for icla in member.iclas.all():
                if icla.is_active:
                    result.append(icla.email)
        return result

    def __str__(self) -> str:
        return self.name


class Person(models.Model):
    class Meta:
        verbose_name_plural = "Personnel"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=255, blank=True)
    joined_at = models.DateField(null=True, blank=True)
    github = models.CharField(unique=True, max_length=255, blank=True, null=True)
    ghe = models.CharField(unique=True, max_length=255, blank=True, null=True, verbose_name="GHE")
    nick = models.CharField(max_length=255, blank=True)
    rev = models.CharField(unique=True, max_length=255, blank=True, null=True)
    pgp = models.CharField(unique=True, max_length=255, blank=True, null=True, verbose_name="PGP")

    groups = models.ManyToManyField(
        Group,
        through="Membership",
        through_fields=("person", "group"),
        related_name="members",
    )

    # here and below are legacy api methods
    @property
    def tags(self) -> dict[str, str]:
        result = {}
        if self.country:
            result["country"] = self.country
        if self.pgp:
            result["pgp"] = self.pgp
        if self.rev:
            result["rev"] = self.rev
        return result

    @property
    def ids(self) -> list[str | dict[str, str]]:
        emails = self.emails.values_list("email", flat=True)
        identities = self.identities.values_list("identity", flat=True)
        result = list(dict.fromkeys(chain(emails, identities)))
        result.append(self.name)
        if self.nick:
            result.append({"nick": self.nick})
        if self.ghe:
            result.append({"ghe": self.ghe})
        if self.github:
            result.append({"github": self.github})
        return result

    @property
    def memberof(self) -> dict[str, str]:
        today = timezone.now().date()
        query_filter = (
            Q(since__isnull=True) | Q(since__lte=today),
            Q(until__isnull=True) | Q(until__gt=today),
        )
        return {m.group.name: str(m.since) for m in self.membership_set.filter(*query_filter)}

    @classmethod
    def list_people(cls) -> list[list[str | dict[str, str]]]:
        return [person.ids for person in cls.objects.all()]

    @classmethod
    def find(cls, id: str) -> Person | None:
        if not id:
            return None
        query_filter = (
            Q(name=id) | Q(nick=id) | Q(ghe=id) | Q(github=id) | Q(emails__email=id) | Q(identities__identity=id)
        )
        queryset = Person.objects.filter(query_filter).distinct()
        if queryset.count() == 1:
            return queryset.first()
        return None

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    since = models.DateField(null=True, blank=True)
    until = models.DateField(null=True, blank=True)


class Identity(models.Model):
    class Meta:
        verbose_name_plural = "Identities"

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="identities")
    identity = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.identity


class Email(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="emails")
    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return self.email
