from __future__ import annotations

import datetime
import logging
import uuid
from pathlib import Path

import requests
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models
from docuseal import docuseal

logger = logging.getLogger(__name__)


def cla_file_name(cla: ICLA | CCLA, filename: str = "") -> str:
    return f"ICLA/{cla.id}.pdf" if isinstance(cla, ICLA) else f"CCLA/{cla.id}/{cla.id}.pdf"


def ccla_attachment_name(ccla_attachment: CCLAAttachment, filename: str = "") -> str:
    return f"CCLA/{ccla_attachment.ccla.id}/{filename}"


def download_document(cla: CCLA | ICLA) -> None:
    docuseal.key = settings.DOCUSEAL_KEY
    docuseal_api_resp = docuseal.get_submission_documents(cla.docuseal_submission_id)
    link = docuseal_api_resp["documents"][0]["url"]
    r = requests.get(link)
    path: Path = settings.MEDIA_ROOT / cla_file_name(cla)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)


class ICLA(models.Model):
    class Meta:
        verbose_name = "ICLA"
        verbose_name_plural = "ICLAs"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cla_pdf = models.FileField("CLA pdf", upload_to=cla_file_name)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=255)
    public_name = models.CharField(blank=True, max_length=255)
    mailing_address = models.CharField(blank=True, max_length=255)
    country = models.CharField(blank=True, max_length=255)
    telephone = models.CharField(blank=True, max_length=255)
    _is_volunteer = models.BooleanField(default=True, verbose_name="Is volunteer")
    docuseal_submission_id = models.IntegerField(blank=True, null=True)
    in_schedule_a = models.BooleanField(default=False, verbose_name="In Schedule A")
    point_of_contact = models.EmailField(blank=True)
    ccla = models.ForeignKey("CCLA", on_delete=models.SET_NULL, blank=True, null=True, verbose_name="CCLA")
    person = models.ForeignKey(
        "personnel.Person",
        on_delete=models.SET_NULL,
        related_name="iclas",
        null=True,
        blank=True,
        verbose_name="Personnel Person",
    )
    signed_at = models.DateTimeField(blank=True, null=True)

    @admin.display(ordering="signed_at")
    def signed_date(self) -> datetime.date | None:
        return self.signed_at.date() if self.signed_at else None

    def create_docuseal_submission(self) -> None:
        logger.info("Create ICLA Docuseal submission for %s", self.email)
        docuseal.key = settings.DOCUSEAL_KEY
        docuseal.create_submission(
            {
                "template_id": settings.DOCUSEAL_ICLA_TEMPLATE_ID,
                "send_email": True,
                "reply_to": settings.CLA_REPLY_TO_EMAIL,
                "submitters": [{"email": self.email, "role": "Contributor", "values": {"Email": self.email}}],
            }
        )

    def send_notification(self) -> None:
        poc = " with point of contact" if self.point_of_contact else ""
        logger.info("%s has signed ICLA%s.", self.email, poc)
        send_mail(
            f"New ICLA{poc}",
            f"{self.email} has signed ICLA.",
            settings.NOTIFICATIONS_SENDER_EMAIL,
            [settings.NOTIFICATIONS_RECIPIENT_EMAIL],
            fail_silently=False,
        )

    def save(self, **kwargs) -> None:
        if not self.cla_pdf and self.docuseal_submission_id:
            download_document(self)
            self.cla_pdf = cla_file_name(self)
        super().save(**kwargs)

    @property
    @admin.display(boolean=True)
    def is_volunteer(self) -> bool:
        return not bool(self.ccla) and bool(self._is_volunteer)

    @property
    @admin.display(boolean=True)
    def is_active(self) -> bool:
        if not self.is_volunteer and self.in_schedule_a and bool(self.cla_pdf):
            return True
        if self.is_volunteer and bool(self.cla_pdf):
            return True
        return False

    def __str__(self) -> str:
        return self.email


class CCLA(models.Model):
    class Meta:
        verbose_name = "CCLA"
        verbose_name_plural = "CCLAs"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    authorized_signer_email = models.EmailField(blank=True)
    authorized_signer_name = models.CharField(blank=True, max_length=255)
    authorized_signer_title = models.CharField(blank=True, max_length=255)
    cla_pdf = models.FileField("CLA pdf", upload_to=cla_file_name)
    corporation_address = models.CharField(blank=True, max_length=255)
    corporation_alias = models.CharField(blank=True, max_length=255)
    corporation_name = models.CharField(unique=True, max_length=255)
    docuseal_submission_id = models.IntegerField(blank=True, null=True)
    fax = models.CharField(blank=True, max_length=255)
    ccla_manager = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="CCLA manager")
    signed_at = models.DateTimeField(blank=True, null=True)
    telephone = models.CharField(blank=True, max_length=255)

    @admin.display(ordering="signed_at")
    def signed_date(self) -> datetime.date | None:
        return self.signed_at.date() if self.signed_at else None

    def create_docuseal_submission(self) -> None:
        logger.info("Create CCLA Docuseal submission for %s", self.corporation_name)
        docuseal.key = settings.DOCUSEAL_KEY
        docuseal.create_submission(
            {
                "template_id": settings.DOCUSEAL_CCLA_TEMPLATE_ID,
                "send_email": True,
                "reply_to": settings.CLA_REPLY_TO_EMAIL,
                "submitters": [
                    {
                        "email": self.ccla_manager.email,
                        "name": f"{self.ccla_manager.first_name} {self.ccla_manager.last_name}",
                        "role": "Authorized Signer",
                        "values": {"Corporation name": self.corporation_name},
                    },
                ],
            }
        )

    def save(self, **kwargs) -> None:
        if not self.cla_pdf and self.docuseal_submission_id:
            download_document(self)
            self.cla_pdf = cla_file_name(self)
        super().save(**kwargs)

    def __str__(self) -> str:
        return self.corporation_name


class CCLAAttachment(models.Model):
    class Meta:
        verbose_name = "CCLA Attachment"
        verbose_name_plural = "CCLA Attachments"

    ccla = models.ForeignKey(CCLA, on_delete=models.CASCADE)
    file = models.FileField(upload_to=ccla_attachment_name)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return Path(self.file.name).name
