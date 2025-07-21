from django.conf import settings
from django.contrib import admin
from django.urls import path

from cla.views import get_csrf_token
from cla.views import handle_ccla_submission_completed_webhook
from cla.views import handle_icla_submission_completed_webhook
from cla.views import send_icla_signing_request


urlpatterns = [
    path("csrf/", get_csrf_token, name="csrf"),
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
