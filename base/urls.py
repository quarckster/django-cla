from django.conf import settings
from django.contrib import admin
from django.urls import path

from api.legacy_api_views import find_person
from api.legacy_api_views import get_email_cla
from api.legacy_api_views import get_group_members
from api.legacy_api_views import get_group_members_cla
from api.legacy_api_views import get_list_clas
from api.legacy_api_views import get_person_cla
from api.legacy_api_views import get_person_membership
from api.legacy_api_views import get_person_tag
from api.legacy_api_views import is_person_in_group
from api.legacy_api_views import list_people
from api.views import handle_github_pull_request_webhook
from api.views import send_message_from_contact_form
from cla.views import get_ccla_pdf
from cla.views import get_icla_pdf
from cla.views import handle_ccla_submission_completed_webhook
from cla.views import handle_icla_submission_completed_webhook
from cla.views import send_icla_signing_request


urlpatterns = [
    path("contact/submit/", send_message_from_contact_form, name="contact-submit"),
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
    path("media/ICLA/<str:filename>", get_icla_pdf, name="media-icla-filename"),
    path("media/CCLA/<str:directory>/<str:filename>", get_ccla_pdf, name="media-ccla-directory-filename"),
    path(
        f"webhooks/icla/{settings.CLA_CHECK_WEBHOOK_SECRET_SLUG}/check/",
        handle_github_pull_request_webhook,
        name="webhooks-icla-check",
    ),
    # legacy API
    path("0/People", list_people, name="0-people"),
    path("0/Person/<str:id>", find_person, name="0-person-id"),
    path("0/Person/<str:id>/Membership", get_person_membership, name="0-person-id-membership"),
    path("0/Person/<str:id>/IsMemberOf/<str:group>", is_person_in_group, name="0-person-id-ismemberof-group"),
    path("0/Person/<str:id>/ValueOfTag/<str:tag>", get_person_tag, name="0-person-id-valueoftag-tag"),
    path("0/Person/<str:id>/HasCLA", get_person_cla, name="0-person-id-hascla"),
    path("0/Group/<str:group>/Members", get_group_members, name="0-group-group-members"),
    path("0/Group/<str:group>/CLAs", get_group_members_cla, name="0-group-group-clas"),
    path("0/HasCLA/<str:email>", get_email_cla, name="0-hascla-email"),
    path("0/CLAs", get_list_clas, name="0-clas"),
]
