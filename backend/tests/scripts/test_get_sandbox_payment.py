from pathlib import Path
import runpy
from unittest.mock import Mock

import httpx
import pytest


PAYMENT_ID = "pay_" + "a" * 26


@pytest.fixture
def script(monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    get = Mock(side_effect=AssertionError("Unexpected GET"))
    post = Mock(side_effect=AssertionError("Read-only script must not POST"))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    path = Path(__file__).resolve().parents[2] / "scripts/2_get_sandbox_payment.py"
    return runpy.run_path(str(path))["main"], get, post


def response(status, data):
    return httpx.Response(status, json=data, request=httpx.Request("GET", "https://checkout.invalid"))


def test_read_only_lookup_prints_selected_balances(script, capsys):
    main, get, post = script
    get.side_effect = None
    get.return_value = response(200, {
        "id": PAYMENT_ID, "status": "Authorized", "currency": "AUD",
        "balances": {"total_authorized": 1000, "total_captured": 0,
                     "total_voided": 0, "available_to_capture": 1000},
        "private": "do-not-print",
    })
    assert main([PAYMENT_ID]) == 0
    get.assert_called_once_with(
        f"https://test.api.sandbox.checkout.com/payments/{PAYMENT_ID}",
        headers={"Authorization": "Bearer sk_sbox_fake"}, timeout=10.0,
    )
    post.assert_not_called()
    output = capsys.readouterr().out
    assert "available_to_capture: 1000" in output
    assert "Status: Authorized" in output
    assert "do-not-print" not in output
    assert "sk_sbox_fake" not in output


def test_invalid_id_sends_no_request(script):
    main, get, post = script
    assert main(["pay_short"]) == 1
    get.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 404, 503])
def test_http_error_stops_without_retry(script, status):
    main, get, post = script
    get.side_effect = None
    get.return_value = response(status, {"private": "do-not-print"})
    assert main([PAYMENT_ID]) == 1
    get.assert_called_once()
    post.assert_not_called()


def test_timeout_does_not_retry_or_write(script, capsys):
    main, get, post = script
    get.side_effect = httpx.ReadTimeout("private-error-detail")
    assert main([PAYMENT_ID]) == 1
    get.assert_called_once()
    post.assert_not_called()
    assert "private-error-detail" not in capsys.readouterr().out


@pytest.mark.parametrize("data", [None, [], {"id": "wrong"}, {"id": PAYMENT_ID}])
def test_malformed_response_does_not_claim_valid_balance(script, data):
    main, get, post = script
    get.side_effect = None
    get.return_value = response(200, data)
    assert main([PAYMENT_ID]) == 1
    post.assert_not_called()
