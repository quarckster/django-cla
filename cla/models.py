import logging
import uuid
from pathlib import Path

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models
from docuseal import docuseal


logger = logging.getLogger(__name__)


def cla_file_name(cla: "CCLA | ICLA", filename: str = "") -> str:
    path = settings.MEDIA_ROOT / type(cla).__name__ / f"{cla.id}.pdf"
    relative = path.relative_to(settings.BASE_DIR)
    return str(relative)


def download_document(cla: "CCLA | ICLA") -> None:
    docuseal.key = settings.DOCUSEAL_KEY
    docuseal_api_resp = docuseal.get_submission_documents(cla.docuseal_submission_id)
    link = docuseal_api_resp["documents"][0]["url"]
    r = requests.get(link)
    Path(cla_file_name(cla)).parent.mkdir(parents=True, exist_ok=True)
    with open(cla_file_name(cla), "wb") as f:
        f.write(r.content)


class ICLA(models.Model):
    class Meta:
        verbose_name = "ICLA"
        verbose_name_plural = "ICLAs"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.CharField()
    docuseal_submission_id = models.IntegerField(blank=True, null=True)
    cla_pdf = models.FileField("CLA pdf", upload_to=cla_file_name)
    email = models.EmailField(unique=True, db_index=True)
    employer_approved_at = models.DateTimeField(blank=True, null=True)
    full_name = models.CharField()
    mailing_address = models.CharField()
    point_of_contact = models.EmailField(blank=True)
    ccla_manager = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True, verbose_name="CCLA manager")
    public_name = models.CharField(blank=True)
    signed_at = models.DateTimeField(blank=True, null=True)
    telephone = models.CharField(blank=True)

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

    def save(self, **kwargs) -> None:
        if not self.cla_pdf and self.docuseal_submission_id:
            download_document(self)
            self.cla_pdf = cla_file_name(self)
        super().save(**kwargs)
        if self.signed_at:
            poc = " with point of contact" if self.point_of_contact else ""
            logger.info("%s has signed ICLA%s.", self.email, poc)
            send_mail(
                f"New ICLA{poc}",
                f"{self.email} has signed ICLA.",
                settings.NOTIFICATIONS_SENDER_EMAIL,
                [settings.NOTIFICATIONS_RECIPIENT_EMAIL],
                fail_silently=False,
            )

    @property
    def is_volunteer(self) -> bool:
        return not bool(self.point_of_contact)

    @property
    def is_active(self) -> bool:
        if not self.is_volunteer and bool(self.employer_approved_at) and bool(self.signed_at):
            return True
        if self.is_volunteer and bool(self.signed_at):
            return True
        return False

    def __str__(self) -> str:
        return f"{self.email}"


class CCLA(models.Model):
    class Meta:
        verbose_name = "CCLA"
        verbose_name_plural = "CCLAs"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    authorized_signer_email = models.EmailField(unique=True)
    authorized_signer_name = models.CharField()
    authorized_signer_title = models.CharField(blank=True)
    cla_pdf = models.FileField("CLA pdf", upload_to=cla_file_name)
    corporation_address = models.CharField()
    corporation_alias = models.CharField(blank=True)
    corporation_name = models.CharField(unique=True)
    docuseal_submission_id = models.IntegerField(blank=True, null=True)
    fax = models.CharField(blank=True)
    ccla_manager = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="CCLA manager")
    signed_at = models.DateTimeField(blank=True, null=True)
    telephone = models.CharField()

    def create_docuseal_submission(self) -> None:
        logger.info("Create CCLA Docuseal submission for %s", self.company)
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
                        "values": {"Corporation name": self.company},
                    },
                ],
            }
        )
