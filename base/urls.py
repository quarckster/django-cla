from django.conf import settings
from django.contrib import admin
from django.urls import path

from cla.views import get_cla_pdf
from cla.views import get_icla_status
from cla.views import handle_ccla_submission_completed_webhook
from cla.views import handle_icla_submission_completed_webhook
from cla.views import send_icla_signing_request


urlpatterns = [
    path("icla/<str:email>/status/", get_icla_status, name="icla-email-status"),
    path("icla/submit/", send_icla_signing_request, name="icla-submit"),
    path(
        f"webhooks/ccla/{settings.CCLA_WEBHOOK_SECRET_SLUG}/",
        handle_ccla_submission_completed_webhook,
        name="webhooks-ccla",
    ),
    path(
        f"webhooks/icla/{settings.ICLA_WEBHOOK_SECRET_SLUG}/",
        handle_icla_submission_completed_webhook,
        name="webhooks-icla",
    ),
    path(f"admin/{settings.ADMIN_SECRET_SLUG}/", admin.site.urls),
    path("media/<str:cla_type>/<str:file_name>/", get_cla_pdf, name="media-cla_type-file_name"),
]
