import uuid

from django.contrib.auth.models import User
from django.db import models


class ICLA(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.TextField()
    docuseal_submission_id = models.IntegerField()
    email = models.EmailField(unique=True, db_index=True)
    employer_approved_at = models.DateTimeField(blank=True, null=True)
    full_name = models.TextField()
    mailing_address = models.TextField()
    point_of_contact = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True)
    public_name = models.TextField(blank=True)
    signed_at = models.DateTimeField(blank=True, null=True)
    telephone = models.TextField(blank=True)


class CCLA(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    authorized_signer_email = models.EmailField(unique=True)
    authorized_signer_name = models.TextField()
    authorized_signer_title = models.TextField(blank=True)
    corporation_address = models.TextField()
    corporation_alias = models.TextField(blank=True)
    corporation_name = models.TextField(unique=True)
    docuseal_submission_id = models.IntegerField()
    fax = models.TextField(blank=True)
    point_of_contact = models.OneToOneField(User, on_delete=models.CASCADE)
    signed_at = models.DateTimeField(blank=True, null=True)
    telephone = models.TextField()
