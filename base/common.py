import logging

import requests
from django.conf import settings
from django.http import HttpRequest


logger = logging.getLogger(__name__)


def verify_turnstile_token(request: HttpRequest) -> bool:
    logger.info("Verify Turnstile token")
    resp = requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={
            "secret": settings.CLOUDFLARE_TURNSTILE_SECRET_KEY,
            "response": request.POST.get("cf-turnstile-response"),
            "remoteip": request.META.get("CF-Connecting-IP"),
        },
        timeout=5,
    )
    result = resp.json()
    return bool(result.get("success"))
