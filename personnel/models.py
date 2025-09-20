import uuid
from itertools import chain

from django.db import models


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Person(models.Model):
    class Meta:
        verbose_name_plural = "Personnel"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=255, blank=True)
    joined_at = models.DateField(null=True, blank=True)
    github = models.CharField(unique=True, max_length=255, blank=True)
    ghe = models.CharField(unique=True, max_length=255, blank=True, verbose_name="GHE")
    nick = models.CharField(max_length=255, blank=True)
    rev = models.CharField(unique=True, max_length=255, blank=True)
    pgp = models.CharField(unique=True, max_length=255, blank=True, verbose_name="PGP")

    groups = models.ManyToManyField(
        Group,
        through="Membership",
        through_fields=("person", "group"),
        related_name="members",
    )

    @property
    def tags(self) -> dict[str, str]:
        return {
            "country": self.country,
            "pgp": self.pgp,
            "rev": self.rev,
        }

    @property
    def ids(self) -> list[str]:
        emails = self.emails.values_list("email", flat=True)
        identities = self.identities.values_list("identity", flat=True)
        return list(dict.fromkeys(chain(emails, identities)))

    def __str__(self):
        return self.name


class Membership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    since = models.DateField(null=True, blank=True)
    until = models.DateField(null=True, blank=True)


class Identity(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="identities")
    identity = models.CharField(max_length=255)

    def __str__(self):
        return self.identity


class Email(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="emails")
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email
