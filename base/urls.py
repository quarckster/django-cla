from django.conf import settings
from django.contrib import admin
from django.urls import path

from cla.views import handle_submission_completed_webhook
from cla.views import render_icla_signing_request_form
from cla.views import send_signing_request_icla

urlpatterns = [
    path("icla/", render_icla_signing_request_form, name="icla"),
    path("icla/submit/", send_signing_request_icla, name="icla-submit"),
    path(
        f"webhooks/icla/{settings.ICLA_WEBHOOK_SECRET_SLUG}/",
        handle_submission_completed_webhook,
        name=f"webhooks-icla-{settings.ICLA_WEBHOOK_SECRET_SLUG}",
    ),
    path("admin/", admin.site.urls),
]
