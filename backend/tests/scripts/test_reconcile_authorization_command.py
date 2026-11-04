from pathlib import Path
import runpy
from unittest.mock import Mock

import httpx
import pytest


PAYMENT_ID = "pay_" + "a" * 26
ARGS = ["--order-id", "order_001", "--amount", "1000", "--currency", "AUD"]


@pytest.fixture
def script(monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    get = Mock(side_effect=AssertionError("Unexpected GET"))
    post = Mock(side_effect=AssertionError("Read-only CLI must not POST"))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    main = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/6_reconcile_authorization.py"))["main"]
    yield main, get
    post.assert_not_called()


def response(code=200, **changes):
    data = {"id": PAYMENT_ID, "reference": "order_001", "amount": 1000,
            "currency": "AUD", "status": "Authorized", "private": "tok_private"}
    return httpx.Response(code, json={**data, **changes}, request=httpx.Request("GET", "https://checkout.invalid"))


@pytest.mark.parametrize("status, expected, exit_code", [
    ("Authorized", "authorized", 0), ("Pending", "pending", 2),
    ("Declined", "declined", 0), ("FutureStatus", "unknown", 2),
])
def test_cli_reports_snapshot_without_secrets(script, capsys, status, expected, exit_code):
    main, get = script
    get.side_effect = None
    get.return_value = response(status=status)
    assert main(ARGS + ["--payment-id", PAYMENT_ID]) == exit_code
    get.assert_called_once()
    output = capsys.readouterr().out
    assert f"Observed status: {expected}" in output
    assert "Next action:" in output
    assert "tok_private" not in output
    assert "sk_sbox_fake" not in output


def test_no_id_needs_no_credentials_or_requests(script, monkeypatch, capsys):
    main, get = script
    monkeypatch.delenv("CHECKOUT_SECRET_KEY")
    assert main(ARGS) == 2
    get.assert_not_called()
    assert "missing_payment_id" in capsys.readouterr().out


@pytest.mark.parametrize("extra", [["--payment-id", "bad"], ["--amount", "0"], ["--order-id", " "]])
def test_invalid_input_stops_before_http(script, extra):
    main, get = script
    assert main(ARGS + extra) == 1
    get.assert_not_called()


def test_invalid_config_stops_before_http(script, monkeypatch):
    main, get = script
    monkeypatch.delenv("CHECKOUT_SECRET_KEY")
    assert main(ARGS + ["--payment-id", PAYMENT_ID]) == 1
    get.assert_not_called()


@pytest.mark.parametrize("code", [401, 403, 404, 429, 503])
def test_lookup_error_stays_unknown_without_retry(script, capsys, code):
    main, get = script
    get.side_effect = None
    get.return_value = response(code)
    assert main(ARGS + ["--payment-id", PAYMENT_ID]) == 2
    get.assert_called_once()
    assert "Observed status: unknown" in capsys.readouterr().out


def test_timeout_hides_details_and_does_not_retry(script, capsys):
    main, get = script
    get.side_effect = httpx.ReadTimeout("private-error")
    assert main(ARGS + ["--payment-id", PAYMENT_ID]) == 2
    get.assert_called_once()
    output = capsys.readouterr().out
    assert "lookup_transport_error" in output
    assert "private-error" not in output


@pytest.mark.parametrize("changes", [{"reference": "other_order"}, {"amount": 1500}, {"currency": "USD"}])
def test_mismatched_payment_is_not_accepted(script, capsys, changes):
    main, get = script
    get.side_effect = None
    get.return_value = response(**changes)
    assert main(ARGS + ["--payment-id", PAYMENT_ID]) == 2
    get.assert_called_once()
    assert "payment_mismatch" in capsys.readouterr().out
