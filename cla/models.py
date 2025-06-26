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
    signed_at = models.DateTimeField(blank=True, null=True)
    address = models.TextField()
    alias = models.TextField(blank=True)
    authorized_signer_email = models.EmailField(unique=True)
    authorized_signer_name = models.TextField()
    country = models.TextField()
    legal_name = models.TextField(unique=True)
    phone = models.TextField()
    point_of_contact = models.OneToOneField(User, on_delete=models.CASCADE)
