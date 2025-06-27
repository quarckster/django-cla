from django.conf import settings
from django.contrib import admin
from django.urls import path

from cla.views import handle_ccla_submission_completed_webhook
from cla.views import handle_icla_submission_completed_webhook
from cla.views import render_ccla_signing_request_form
from cla.views import render_icla_signing_request_form
from cla.views import send_ccla_signing_request
from cla.views import send_icla_signing_request


urlpatterns = [
    path("ccla/", render_ccla_signing_request_form, name="ccla"),
    path("icla/", render_icla_signing_request_form, name="icla"),
    path("ccla/submit/", send_ccla_signing_request, name="ccla-submit"),
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
    path("admin/", admin.site.urls),
]
