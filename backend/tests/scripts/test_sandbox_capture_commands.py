from pathlib import Path
import runpy
from unittest.mock import Mock

import httpx
import pytest


PAYMENT_ID = "pay_" + "a" * 26
ACTION_ID = "act_" + "b" * 26
OPTIONS = ["--amount", "1000", "--reference", "capture_order_001"]


def response(status, data):
    return httpx.Response(status, json=data, request=httpx.Request("GET", "https://checkout.invalid"))


@pytest.fixture
def scripts(monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    get = Mock(side_effect=AssertionError("Unexpected GET"))
    post = Mock(side_effect=AssertionError("Unexpected POST"))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    directory = Path(__file__).resolve().parents[2] / "scripts"
    capture = runpy.run_path(str(directory / "3_capture_sandbox_payment.py"))["main"]
    confirm = runpy.run_path(str(directory / "4_confirm_sandbox_capture.py"))["main"]
    return capture, confirm, get, post


def authorized():
    return {
        "id": PAYMENT_ID, "status": "Authorized", "currency": "AUD",
        "balances": {"total_authorized": 1000, "total_captured": 0,
                     "total_voided": 0, "available_to_capture": 1000},
    }


def test_capture_command_prints_action_id_and_submits_once(scripts, capsys):
    capture, _, get, post = scripts
    get.side_effect = None
    get.return_value = response(200, authorized())
    post.side_effect = None
    post.return_value = response(202, {"action_id": ACTION_ID})
    assert capture([PAYMENT_ID, *OPTIONS]) == 0
    get.assert_called_once()
    post.assert_called_once()
    output = capsys.readouterr().out
    assert "Request status: accepted" in output
    assert "Action ID: " + ACTION_ID in output
    assert "sk_sbox_fake" not in output


def test_capture_command_timeout_reports_unknown_without_retry(scripts, capsys):
    capture, _, get, post = scripts
    get.side_effect = None
    get.return_value = response(200, authorized())
    post.side_effect = httpx.ReadTimeout("private-detail")
    assert capture([PAYMENT_ID, *OPTIONS]) == 2
    post.assert_called_once()
    output = capsys.readouterr().out
    assert "Request status: unknown" in output
    assert "private-detail" not in output


@pytest.mark.parametrize("status", [401, 403, 503])
def test_capture_command_lookup_failure_does_not_post(scripts, status):
    capture, _, get, post = scripts
    get.side_effect = None
    get.return_value = response(status, {})
    assert capture([PAYMENT_ID, *OPTIONS]) == 1
    get.assert_called_once()
    post.assert_not_called()


def test_capture_command_blocks_ineligible_payment(scripts):
    capture, _, get, post = scripts
    data = authorized()
    data["status"] = "Captured"
    get.side_effect = None
    get.return_value = response(200, data)
    assert capture([PAYMENT_ID, *OPTIONS]) == 1
    post.assert_not_called()


@pytest.mark.parametrize("which", ["capture", "confirm"])
def test_invalid_id_does_not_send_http(scripts, which):
    capture, confirm, get, post = scripts
    if which == "capture":
        assert capture(["invalid", *OPTIONS]) == 1
    else:
        assert confirm([PAYMENT_ID, "invalid", *OPTIONS]) == 1
    get.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("approved,expected,exit_code", [
    (True, "succeeded", 0), (False, "failed", 1), (None, "unknown", 2),
])
def test_confirmation_command_is_read_only(scripts, capsys, approved, expected, exit_code):
    _, confirm, get, post = scripts
    get.side_effect = None
    get.return_value = response(200, [{
        "id": ACTION_ID, "type": "Capture", "amount": 1000, "approved": approved,
    }])
    assert confirm([PAYMENT_ID, ACTION_ID, *OPTIONS]) == exit_code
    get.assert_called_once()
    post.assert_not_called()
    output = capsys.readouterr().out
    assert "Confirmation: " + expected in output
    assert "sk_sbox_fake" not in output


def test_confirmation_timeout_remains_unknown_and_does_not_post(scripts):
    _, confirm, get, post = scripts
    get.side_effect = httpx.ReadTimeout("private-detail")
    assert confirm([PAYMENT_ID, ACTION_ID, *OPTIONS]) == 2
    get.assert_called_once()
    post.assert_not_called()
