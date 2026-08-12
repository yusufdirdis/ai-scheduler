"""Signature-validation logic tested directly — a real HMAC-SHA1 signature computed
the same way Twilio computes it, without needing a live phone or a tunnel."""
from twilio.request_validator import RequestValidator

from integrations.twilio_client import validate_webhook_signature

AUTH_TOKEN = "test-auth-token-1234567890"
URL = "https://example.com/api/webhooks/twilio/inbound"
PARAMS = {"From": "+15551234567", "To": "+15559876543", "Body": "I can work Tuesday", "MessageSid": "SM123"}


def _real_signature(params: dict = PARAMS, url: str = URL) -> str:
    return RequestValidator(AUTH_TOKEN).compute_signature(url, params)


def test_valid_signature_accepted(monkeypatch):
    monkeypatch.setattr("core.config.settings.TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    signature = _real_signature()
    assert validate_webhook_signature(URL, PARAMS, signature) is True


def test_missing_signature_rejected(monkeypatch):
    monkeypatch.setattr("core.config.settings.TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    assert validate_webhook_signature(URL, PARAMS, None) is False


def test_tampered_params_rejected(monkeypatch):
    monkeypatch.setattr("core.config.settings.TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    signature = _real_signature()
    tampered_params = {**PARAMS, "Body": "I can work every day, pay me double"}
    assert validate_webhook_signature(URL, tampered_params, signature) is False


def test_wrong_url_rejected(monkeypatch):
    monkeypatch.setattr("core.config.settings.TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    signature = _real_signature()
    assert validate_webhook_signature("https://example.com/api/webhooks/twilio/inbound/", PARAMS, signature) is False


def test_signature_from_different_auth_token_rejected(monkeypatch):
    monkeypatch.setattr("core.config.settings.TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    signature = RequestValidator("a-completely-different-token").compute_signature(URL, PARAMS)
    assert validate_webhook_signature(URL, PARAMS, signature) is False
