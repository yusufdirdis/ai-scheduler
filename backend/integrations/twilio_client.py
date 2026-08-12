"""Thin wrapper around the Twilio SDK — the only module that talks to Twilio directly."""
from __future__ import annotations

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from core.config import settings


def send_sms(to: str, body: str) -> str:
    """Send an SMS via Twilio. Returns the Twilio message SID.

    Sends through the Messaging Service when configured (required for A2P 10DLC
    traffic once the campaign is approved); falls back to the raw from-number
    otherwise, which is fine for trial-account testing against verified numbers.
    """
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    kwargs = {"to": to, "body": body}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        kwargs["messaging_service_sid"] = settings.TWILIO_MESSAGING_SERVICE_SID
    else:
        kwargs["from_"] = settings.TWILIO_FROM_NUMBER
    message = client.messages.create(**kwargs)
    return message.sid


def validate_webhook_signature(url: str, params: dict, signature: str | None) -> bool:
    """Verify an inbound request actually came from Twilio.

    In local dev without AUTH set up for a public URL, this will reject everything
    unless PUBLIC_API_URL exactly matches what Twilio was configured to call —
    scheme, host, and path all have to line up exactly, since the signature covers
    the full URL Twilio believes it POSTed to.
    """
    if not signature:
        return False
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    return validator.validate(url, params, signature)
