from pathlib import Path
import runpy
from unittest.mock import Mock

import httpx
import pytest


@pytest.fixture
def sandbox_script(monkeypatch):
    # Block all real HTTP calls, even if a test forgets to configure a response.
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "pk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PROCESSING_CHANNEL_ID", "pc_" + "a" * 26)
    post = Mock(side_effect=AssertionError("Unexpected HTTP POST"))
    get = Mock(side_effect=AssertionError("Unexpected HTTP GET"))
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "get", get)
    path = Path(__file__).resolve().parents[2] / "scripts/1_create_sandbox_payment.py"
    return runpy.run_path(str(path))["main"], post, get


def response(status, data):
    request = httpx.Request("POST", "https://test.api.sandbox.checkout.com/payments")
    return httpx.Response(status, json=data, request=request)


def test_script_creates_record_then_looks_up_same_payment(sandbox_script, capsys):
    main, post, get = sandbox_script
    payment_id = "pay_" + "a" * 26
    data = {"id": payment_id, "status": "Authorized"}
    post.side_effect = [response(201, {"token": "tok_fake"}), response(201, data)]
    get.side_effect = None
    get.return_value = response(200, data)

    assert main() == 0

    assert post.call_count == 2  # One token request and one payment request.
    assert post.call_args.kwargs["json"]["capture"] is False
    assert post.call_args.kwargs["json"]["reference"].startswith("sandbox_order_")
    get.assert_called_once_with(
        "https://test.api.sandbox.checkout.com/payments/" + payment_id,
        headers={"Authorization": "Bearer sk_sbox_fake"}, timeout=10.0,
    )
    assert "Local status: authorized" in capsys.readouterr().out


@pytest.mark.parametrize("status,category", [
    (401, "authentication_error"), (403, "permission_error"),
    (422, "invalid_request"), (429, "rate_limited"), (503, "uncertain_outcome"),
])
def test_script_classifies_error_without_retry(sandbox_script, capsys, status, category):
    main, post, get = sandbox_script
    post.side_effect = [response(201, {"token": "tok_fake"}), response(status, {})]

    assert main() == 1

    assert post.call_count == 2
    get.assert_not_called()
    output = capsys.readouterr().out
    assert "Error category: " + category in output
    assert "No automatic retry was attempted." in output


def test_script_timeout_does_not_create_another_payment(sandbox_script, capsys):
    main, post, get = sandbox_script
    post.side_effect = [response(201, {"token": "tok_fake"}), httpx.ReadTimeout("private")]

    assert main() == 1

    assert post.call_count == 2
    get.assert_not_called()
    output = capsys.readouterr().out
    assert "Reconcile" in output
    assert "private" not in output


def test_script_incomplete_payment_response_preserves_id_for_reconciliation(sandbox_script, capsys):
    main, post, get = sandbox_script
    payment_id = "pay_" + "a" * 26
    post.side_effect = [response(201, {"token": "tok_fake"}), response(201, {"id": payment_id})]

    assert main() == 1

    assert post.call_count == 2
    get.assert_not_called()
    output = capsys.readouterr().out
    assert "Payment ID: " + payment_id in output
    assert "Do not rerun blindly" in output
