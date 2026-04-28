from application.billing_use_cases import confirmar_pagamento_checkout


def processar_webhook_pagamento(provider, payload):
    provider = str(provider or "").upper()

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
