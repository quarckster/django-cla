import json
from typing import Any
from typing import TypedDict

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse
from pytest_mock import MockerFixture

from api import cla_check
from cla.models import ICLA


@pytest.fixture(autouse=True)
def set_settings(monkeypatch):
    monkeypatch.setenv("DJANGO_ICLA_WEBHOOK_SECRET_SLUG", "test_secret_slug")
    monkeypatch.setenv("DJANGO_GITHUB_API_TOKEN", "dummy_token")


@pytest.fixture
def client_url() -> str:
    return reverse("webhooks-icla-check")


HEADERS = {
    "X_GITHUB_EVENT": "pull_request",
    "CONTENT_TYPE": "application/json",
}

PR = TypedDict("PR", {"commits_url": str, "issue_url": str, "_links": dict[str, dict[str, str]]})

FAKE_PR: PR = {
    "commits_url": "https://api.github.com/repos/openssl/openssl/pulls/123/commits",
    "issue_url": "https://api.github.com/repos/openssl/openssl/issues/123",
    "_links": {"statuses": {"href": "https://api.github.com/repos/openssl/openssl/statuses/sha123"}},
}


def _commit(email: str, message: str) -> dict[str, Any]:
    return {"commit": {"author": {"email": email}, "message": message}}


class _Resp:
    def __init__(self, *, json_data=None, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json


@pytest.mark.django_db
def test_process_cla_trivial(client: Client, mocker: MockerFixture):
    """Single trivial commit -> success status + remove label."""
    commits = [_commit("user@example.com", "fix: typo\n\nCLA: Trivial")]
    payload = {"action": "opened", "pull_request": FAKE_PR}
    body = json.dumps(payload).encode("utf-8")

    # Mock GitHub API calls used by api.cla_check.process()
    m_get = mocker.patch("requests.get", return_value=_Resp(json_data=commits))
    m_post = mocker.patch("requests.post")
    m_del = mocker.patch("requests.delete", return_value=_Resp(status_code=200))

    resp = client.post(reverse("webhooks-icla-check"), body, content_type="application/json", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.content == b"ok"

    # requests.get called for commits
    m_get.assert_called_once_with(FAKE_PR["commits_url"], headers=cla_check.get_headers(settings.GITHUB_API_TOKEN))

    # One POST for statuses; NO POST to labels endpoint
    status_url = FAKE_PR["_links"]["statuses"]["href"]
    assert any(call.args[0] == status_url for call in m_post.mock_calls)
    assert not any((call.args[0] == f'{FAKE_PR["issue_url"]}/labels') for call in m_post.mock_calls)

    # DELETE called to remove label
    assert any(call.args[0].startswith(f'{FAKE_PR["issue_url"]}/labels/') for call in m_del.mock_calls)


@pytest.mark.django_db
def test_process_missing_cla(client: Client, mocker: MockerFixture):
    """Non-trivial commit + no ICLA in DB -> failure + add label."""
    commits = [_commit("missing@example.com", "implement feature")]
    payload = {"action": "opened", "pull_request": FAKE_PR}
    body = json.dumps(payload).encode("utf-8")

    mocker.patch("requests.get", return_value=_Resp(json_data=commits))
    m_post = mocker.patch("requests.post")
    m_del = mocker.patch("requests.delete")  # should NOT be used in this path

    # DB: let ICLA lookup 404 naturally (empty DB)
    resp = client.post(reverse("webhooks-icla-check"), body, content_type="application/json", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.content == b"ok"

    # Status updated (POST to statuses) and label added (POST to labels)
    status_url = FAKE_PR["_links"]["statuses"]["href"]
    labels_url = f'{FAKE_PR["issue_url"]}/labels'
    assert any(call.args[0] == status_url for call in m_post.mock_calls)
    assert any(call.args[0] == labels_url for call in m_post.mock_calls)
    # No delete
    assert not m_del.mock_calls


@pytest.mark.django_db
def test_process_cla_in_db(client: Client, mocker: MockerFixture):
    """Non-trivial commit + ICLA in DB and active -> success + remove label."""
    commits = [_commit("known@example.com", "normal message")]
    payload = {"action": "opened", "pull_request": FAKE_PR}
    body = json.dumps(payload).encode("utf-8")

    mocker.patch("requests.get", return_value=_Resp(json_data=commits))
    m_post = mocker.patch("requests.post")
    m_del = mocker.patch("requests.delete")

    # ORM: emulate found & active ICLA
    mock_icla = mocker.MagicMock()
    mock_icla.is_active = True
    mocker.patch.object(ICLA.objects, "get", return_value=mock_icla)

    resp = client.post(reverse("webhooks-icla-check"), body, content_type="application/json", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.content == b"ok"

    status_url = FAKE_PR["_links"]["statuses"]["href"]
    assert any(call.args[0] == status_url for call in m_post.mock_calls)
    # Label removed
    assert any(call.args[0].startswith(f'{FAKE_PR["issue_url"]}/labels/') for call in m_del.mock_calls)
    # No label add
    assert not any(call.args[0] == f'{FAKE_PR["issue_url"]}/labels' for call in m_post.mock_calls)


@pytest.mark.django_db
def test_process_cla_multiple_commits_non_trivial(client: Client, mocker: MockerFixture):
    """
    Multiple commits, both non-trivial; one email has CLA, the other does not -> failure + add label.
    """
    commits = [
        _commit("withcla@example.com", "feature A"),
        _commit("nacla@example.com", "feature B"),
    ]
    payload = {"action": "opened", "pull_request": FAKE_PR}
    body = json.dumps(payload).encode("utf-8")

    mocker.patch("requests.get", return_value=_Resp(json_data=commits))
    m_post = mocker.patch("requests.post")
    m_del = mocker.patch("requests.delete")

    # ORM behavior:
    # withcla@example.com => found active
    # nacla@example.com   => raise DoesNotExist
    def _get(email: str, **_):
        if email == "withcla@example.com":
            o = mocker.MagicMock()
            o.is_active = True
            return o
        raise ICLA.DoesNotExist

    mocker.patch.object(ICLA.objects, "get", side_effect=_get)

    resp = client.post(reverse("webhooks-icla-check"), body, content_type="application/json", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.content == b"ok"

    # Failure status and add_label invoked
    status_url = FAKE_PR["_links"]["statuses"]["href"]
    labels_url = f'{FAKE_PR["issue_url"]}/labels'
    assert any(call.args[0] == status_url for call in m_post.mock_calls)
    assert any(call.args[0] == labels_url for call in m_post.mock_calls)
    # No remove_label
    assert not m_del.mock_calls


@pytest.mark.django_db
def test_process_cla_multiple_commits_all_trivial(client: Client, mocker: MockerFixture):
    """Multiple commits all trivial -> success + remove label."""
    commits = [
        _commit("a@example.com", "CLA: trivial\n\nsmall tweak"),
        _commit("b@example.com", "docs update\n\ncla: TRIVIAL"),
    ]
    payload = {"action": "opened", "pull_request": FAKE_PR}
    body = json.dumps(payload).encode("utf-8")

    mocker.patch("requests.get", return_value=_Resp(json_data=commits))
    m_post = mocker.patch("requests.post")
    m_del = mocker.patch("requests.delete", return_value=_Resp(status_code=200))

    # DB: irrelevant since everything is trivial, but keep it harmless
    mocker.patch.object(ICLA.objects, "get", side_effect=ICLA.DoesNotExist)

    resp = client.post(reverse("webhooks-icla-check"), body, content_type="application/json", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.content == b"ok"

    status_url = FAKE_PR["_links"]["statuses"]["href"]
    assert any(call.args[0] == status_url for call in m_post.mock_calls)
    # Remove label was called
    assert any(call.args[0].startswith(f'{FAKE_PR["issue_url"]}/labels/') for call in m_del.mock_calls)
    # No label add
    assert not any(call.args[0] == f'{FAKE_PR["issue_url"]}/labels' for call in m_post.mock_calls)
