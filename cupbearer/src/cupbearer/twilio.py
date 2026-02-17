from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TwilioAPIError(RuntimeError):
    """Raised when Twilio returns an error response."""


def normalize_whatsapp_address(value: str) -> str:
    """Ensure Twilio WhatsApp address format, e.g. whatsapp:+15551234567."""
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("WhatsApp address cannot be empty")
    if trimmed.startswith("whatsapp:"):
        return trimmed
    return f"whatsapp:{trimmed}"


def compute_signature(url: str, params: dict[str, str], auth_token: str) -> str:
    """Compute the Twilio request signature for x-www-form-urlencoded webhooks."""
    chunks = [url]
    for key in sorted(params):
        chunks.append(key)
        chunks.append(params[key])

    payload = "".join(chunks).encode("utf-8")
    digest = hmac.new(auth_token.encode("utf-8"), payload, hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def validate_signature(
    *, url: str, params: dict[str, str], auth_token: str, provided_signature: str | None
) -> bool:
    if not provided_signature:
        return False
    expected = compute_signature(url=url, params=params, auth_token=auth_token)
    return hmac.compare_digest(expected, provided_signature)


def _twilio_request(
    *,
    account_sid: str,
    auth_token: str,
    method: str,
    path: str,
    form: dict[str, str] | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    endpoint = f"https://api.twilio.com{path}"
    body = None
    headers = {"Accept": "application/json"}
    if form is not None:
        body = urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = Request(endpoint, method=method, data=body, headers=headers)
    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode(
        "utf-8"
    )
    request.add_header("Authorization", f"Basic {credentials}")

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as err:
        details = err.read().decode("utf-8")
        raise TwilioAPIError(f"Twilio API request failed ({err.code}): {details}") from err


def fetch_account(account_sid: str, auth_token: str, timeout_seconds: float = 10.0) -> dict[str, Any]:
    return _twilio_request(
        account_sid=account_sid,
        auth_token=auth_token,
        method="GET",
        path=f"/2010-04-01/Accounts/{account_sid}.json",
        timeout_seconds=timeout_seconds,
    )


def send_whatsapp_message(
    *,
    account_sid: str,
    auth_token: str,
    from_whatsapp: str,
    to_whatsapp: str,
    body: str,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    return _twilio_request(
        account_sid=account_sid,
        auth_token=auth_token,
        method="POST",
        path=f"/2010-04-01/Accounts/{account_sid}/Messages.json",
        form={
            "From": normalize_whatsapp_address(from_whatsapp),
            "To": normalize_whatsapp_address(to_whatsapp),
            "Body": body,
        },
        timeout_seconds=timeout_seconds,
    )
