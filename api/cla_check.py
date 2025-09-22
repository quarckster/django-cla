import logging
import re
from urllib.parse import quote

import requests

from base import settings
from cla.models import ICLA

logger = logging.getLogger(__name__)


CLA_LABEL = "hold: cla required"
TRIVIAL = re.compile(r"^\s*CLA\s*:\s*TRIVIAL", re.IGNORECASE | re.MULTILINE)
SUCCESS = "success"
FAILURE = "failure"


def get_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def remove_label(pr: dict) -> None:
    url = f"{pr['issue_url']}/labels/{quote(CLA_LABEL)}"
    logger.info("Remove label %s", url)
    r = requests.delete(url, headers=get_headers(settings.GITHUB_COM_TOKEN))
    if r.status_code == 404:
        logger.info("Label %s doesn't exist", url)


def add_label(pr: dict) -> None:
    payload = f'[ "{CLA_LABEL}" ]'
    url = f"{pr['issue_url']}/labels"
    logger.info("Add label %s", url)
    requests.post(url, data=payload, headers=get_headers(settings.GITHUB_COM_TOKEN))


def update_status(pr: dict, state: str, description: str) -> None:
    payload = {
        "state": state,
        "target_url": "https://openssl-library.org/policies/cla/",
        "description": description,
        "context": "cla-check",
    }
    url = pr["_links"]["statuses"]["href"]
    logger.info("Update commit status of CLA check: %s, %s, %s", url, state, description)
    requests.post(url, json=payload, headers=get_headers(settings.GITHUB_COM_TOKEN))


def is_in_cla_db(email: str) -> bool:
    try:
        icla = ICLA.objects.get(email=email)
        logger.info("%s is found in the CLA DB, active - %s", email.lower(), icla.is_active)
        return icla.is_active
    except ICLA.DoesNotExist:
        logger.info("%s is not found in the CLA DB", email.lower())
        return False


def get_pr_commits(commits_url: str) -> dict:
    headers = get_headers(settings.GITHUB_COM_TOKEN)
    r = requests.get(commits_url, headers=headers)
    return r.json()


def process(pr: dict) -> None:
    alltrivial = True
    missing = set()
    commits_url = pr["commits_url"]
    items = get_pr_commits(commits_url)
    for item in items:
        email = item["commit"]["author"]["email"]
        msg = item["commit"]["message"]
        if not TRIVIAL.search(msg):
            alltrivial = False
            if not is_in_cla_db(email):
                missing.add(email)
    if alltrivial:
        update_status(pr, SUCCESS, "Trivial")
        remove_label(pr)
    elif not missing:
        update_status(pr, SUCCESS, "CLA found")
        remove_label(pr)
    else:
        update_status(pr, FAILURE, f"CLA missing: {', '.join(missing)}")
        add_label(pr)
