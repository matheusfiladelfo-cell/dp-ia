import hashlib
import hmac
import os

from application.billing_use_cases import confirmar_pagamento_checkout


def _normalize_headers(headers):
    normalized = {}
    for k, v in (headers or {}).items():
        normalized[str(k).strip().lower()] = "" if v is None else str(v).strip()
    return normalized


def _extract_bearer_token(headers):
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _is_local_safe_mode():
    env = str(os.getenv("APP_ENV", "")).strip().lower()
    return env in {"local", "dev", "development", "test"}


def _validate_webhook_auth(provider, payload, headers=None):
    """
    Valida token/assinatura de webhook sem vazar segredos em log.
    Regras:
    - Se token/secret estiver configurado no ambiente, valida obrigatoriamente.
    - Sem configuração, só permite em ambiente local seguro.
    """
    provider = str(provider or "").upper()
    hdrs = _normalize_headers(headers or payload.get("headers") or payload.get("__headers__") or {})

    token_env_by_provider = {
        "ASAAS": os.getenv("ASAAS_WEBHOOK_TOKEN", "").strip(),
        "MERCADO_PAGO": os.getenv("MP_WEBHOOK_TOKEN", "").strip(),
        "MERCADOPAGO": os.getenv("MP_WEBHOOK_TOKEN", "").strip(),
    }
    token_expected = token_env_by_provider.get(provider, "")

    if token_expected:
        token_received = (
            hdrs.get("x-webhook-token")
            or hdrs.get("x-api-key")
            or _extract_bearer_token(hdrs)
            or ""
        ).strip()
        if not token_received:
            print(f"[webhook] auth inválida: token ausente provider={provider}")
            return False
        if not hmac.compare_digest(token_received, token_expected):
            print(f"[webhook] auth inválida: token divergente provider={provider}")
            return False
        return True

    # Assinatura HMAC opcional (quando disponível payload bruto)
    hmac_env_by_provider = {
        "ASAAS": os.getenv("ASAAS_WEBHOOK_HMAC_SECRET", "").strip(),
        "MERCADO_PAGO": os.getenv("MP_WEBHOOK_HMAC_SECRET", "").strip(),
        "MERCADOPAGO": os.getenv("MP_WEBHOOK_HMAC_SECRET", "").strip(),
    }
    hmac_secret = hmac_env_by_provider.get(provider, "")
    if hmac_secret:
        raw_body = payload.get("__raw_body__")
        signature = hdrs.get("x-signature", "").strip()
        if not raw_body or not signature:
            print(f"[webhook] auth inválida: assinatura/raw ausente provider={provider}")
            return False
        digest = hmac.new(
            hmac_secret.encode("utf-8"),
            str(raw_body).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, digest):
            print(f"[webhook] auth inválida: assinatura divergente provider={provider}")
            return False
        return True

    if _is_local_safe_mode():
        print(f"[webhook] auth bypass local seguro provider={provider}")
        return True

    print(f"[webhook] auth inválida: secret/token não configurado provider={provider}")
    return False


def processar_webhook_pagamento(provider, payload, headers=None):
    provider = str(provider or "").upper()
    payload = payload or {}

    if not _validate_webhook_auth(provider, payload, headers=headers):
        return {"ok": False, "error": "Webhook não autenticado"}

    if provider == "ASAAS":
        event = payload.get("event")
        payment = payload.get("payment", {})
        reference = payment.get("externalReference") or payload.get("externalReference")
        status = payment.get("status") or event
        external_subscription_id = payment.get("subscription")
        return confirmar_pagamento_checkout(reference, status, external_subscription_id)

    if provider in {"MERCADO_PAGO", "MERCADOPAGO"}:
        data = payload.get("data", {})
        reference = (
            payload.get("external_reference")
            or data.get("external_reference")
            or payload.get("externalReference")
        )
        status = payload.get("status") or data.get("status")
        external_subscription_id = payload.get("id") or data.get("id")
        return confirmar_pagamento_checkout(reference, status, external_subscription_id)

    return {"ok": False, "error": "Provider de webhook não suportado"}
