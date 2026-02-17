from __future__ import annotations

import os

import pytest

from cupbearer.twilio import fetch_account


@pytest.mark.e2e
@pytest.mark.twilio_live
def test_live_twilio_credentials_can_fetch_account() -> None:
    if os.getenv("CUPBEARER_RUN_LIVE_TWILIO_TESTS") != "1":
        pytest.skip("Set CUPBEARER_RUN_LIVE_TWILIO_TESTS=1 to run live Twilio smoke tests")

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    assert account_sid, "Missing TWILIO_ACCOUNT_SID"
    assert auth_token, "Missing TWILIO_AUTH_TOKEN"

    account = fetch_account(account_sid=account_sid, auth_token=auth_token)

    assert account["sid"] == account_sid
    assert account["status"] in {"active", "suspended", "closed"}
