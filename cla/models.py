import logging
import uuid

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models
from docuseal import docuseal


logger = logging.getLogger(__name__)


class ICLA(models.Model):
    class Meta:
        verbose_name_plural = "ICLAs"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.CharField()
    docuseal_submission_id = models.IntegerField()
    email = models.EmailField(unique=True, db_index=True)
    employer_approved_at = models.DateTimeField(blank=True, null=True)
    full_name = models.CharField()
    mailing_address = models.CharField()
    point_of_contact = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True)
    public_name = models.CharField(blank=True)
    signed_at = models.DateTimeField(blank=True, null=True)
    telephone = models.CharField(blank=True)

    def save(self, **kwargs):
        super().save(**kwargs)
        send_mail(
            "New ICLA",
            f"{self.email} has signed ICLA.",
            settings.NOTIFICATIONS_SENDER_EMAIL,
            [settings.NOTIFICATIONS_RECIPIENT_EMAIL],
            fail_silently=False,
        )
        download_document(self)

    @property
    def is_volunteer(self) -> bool:
        return self.employer_approved_at is None

    def __str__(self) -> str:
        return f"{self.email}"


class CCLA(models.Model):
    class Meta:
        verbose_name_plural = "CCLAs"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    authorized_signer_email = models.EmailField(unique=True)
    authorized_signer_name = models.CharField()
    authorized_signer_title = models.CharField(blank=True)
    corporation_address = models.CharField()
    corporation_alias = models.CharField(blank=True)
    corporation_name = models.CharField(unique=True)
    docuseal_submission_id = models.IntegerField()
    fax = models.CharField(blank=True)
    point_of_contact = models.OneToOneField(User, on_delete=models.CASCADE)
    signed_at = models.DateTimeField(blank=True, null=True)
    telephone = models.CharField()


def download_document(cla: CCLA | ICLA) -> None:
    docuseal.key = settings.DOCUSEAL_KEY
    docuseal_api_resp = docuseal.get_submission_documents(cla.docuseal_submission_id)
    link = docuseal_api_resp["documents"][0]["url"]
    r = requests.get(link)
    file_name = cla.email if isinstance(cla, ICLA) else cla.corporation_name
    with open(f"{settings.DOCUMENTS_PATH}/{file_name}.pdf", "wb") as f:
        f.write(r.content)
