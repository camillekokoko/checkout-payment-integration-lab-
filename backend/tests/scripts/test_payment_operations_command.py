from pathlib import Path
import runpy
from unittest.mock import Mock

import httpx
import pytest


PAYMENT_ID = "pay_" + "a" * 26
ACTION_ID = "act_" + "b" * 26


def response(status, data):
    return httpx.Response(status, json=data, request=httpx.Request("GET", "https://checkout.invalid"))


@pytest.fixture
def script(monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    get = Mock(side_effect=AssertionError("Unexpected GET"))
    post = Mock(side_effect=AssertionError("Unexpected POST"))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    path = Path(__file__).resolve().parents[2] / "scripts/5_payment_operations.py"
    return runpy.run_path(str(path))["main"], get, post


@pytest.mark.parametrize("command,amount", [("partial-capture", 500), ("void", 1000), ("refund", 400)])
def test_operation_command_sends_one_write(script, command, amount, capsys):
    main, get, post = script
    get.side_effect = None
    get.return_value = response(200, {
        "id": PAYMENT_ID, "currency": "AUD", "source": {"type": "card"},
        "status": "Captured" if command == "refund" else "Authorized",
        "balances": {"total_authorized": 1000, "total_voided": 0,
                     "total_captured": 1000 if command == "refund" else 0,
                     "available_to_capture": 1000, "available_to_void": 1000,
                     "total_refunded": 0, "available_to_refund": 1000},
    })
    post.side_effect = None
    post.return_value = response(202, {"action_id": ACTION_ID})
    assert main([command, PAYMENT_ID, "--amount", str(amount), "--reference", "operation_001"]) == 0
    get.assert_called_once()
    post.assert_called_once()
    assert "Request status: accepted" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["Capture", "Void", "Refund"])
def test_confirm_command_only_reads(script, kind, capsys):
    main, get, post = script
    get.side_effect = None
    get.return_value = response(200, [{"id": ACTION_ID, "type": kind, "amount": 500, "approved": True}])
    assert main(["confirm", PAYMENT_ID, "--action-id", ACTION_ID, "--action-type", kind,
                 "--amount", "500", "--reference", "operation_001"]) == 0
    get.assert_called_once()
    post.assert_not_called()
    assert "Confirmation: succeeded" in capsys.readouterr().out


def test_command_unknown_outcome_does_not_retry(script, capsys):
    main, get, post = script
    get.side_effect = None
    get.return_value = response(200, {"id": PAYMENT_ID, "currency": "AUD", "source": {"type": "card"},
        "status": "Captured", "balances": {"total_captured": 1000, "total_refunded": 0, "available_to_refund": 1000}})
    post.side_effect = httpx.ReadTimeout("private-detail")
    assert main(["refund", PAYMENT_ID, "--amount", "500", "--reference", "refund_001"]) == 2
    post.assert_called_once()
    output = capsys.readouterr().out
    assert "Outcome uncertain" in output
    assert "private-detail" not in output


def test_bad_input_does_not_send_any_request(script):
    main, get, post = script
    assert main(["void", "invalid", "--amount", "1000", "--reference", "void_001"]) == 1
    get.assert_not_called()
    post.assert_not_called()
