import os
import uuid

import requests
from config_pricing import PRO, PREMIUM


PROVIDER_ASAAS = "ASAAS"
PROVIDER_MERCADO_PAGO = "MERCADO_PAGO"

PLANOS_PRECO = {
    "PRO": float(PRO),
    "PREMIUM": float(PREMIUM),
}


def _simular_checkout(base_url, external_reference):
    return f"{base_url}?ref={external_reference}"


def gerar_checkout_link(provider, plano, email_cliente, external_reference):
    provider = str(provider or PROVIDER_ASAAS).upper()
    valor = PLANOS_PRECO.get(plano, 0.0)

    if provider == PROVIDER_ASAAS:
        return _gerar_checkout_asaas(plano, email_cliente, valor, external_reference)

    if provider == PROVIDER_MERCADO_PAGO:
        return _gerar_checkout_mercado_pago(plano, email_cliente, valor, external_reference)

    return {
        "ok": False,
        "provider": provider,
        "error": "Provider inválido",
    }


def _gerar_checkout_asaas(plano, email_cliente, valor, external_reference):
    api_key = os.getenv("ASAAS_API_KEY")
    base_url = os.getenv("ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3")
    frontend_fallback = os.getenv("ASAAS_FAKE_CHECKOUT_URL", "https://sandbox.asaas.com")

    if not api_key:
        return {
            "ok": True,
            "provider": PROVIDER_ASAAS,
            "checkout_url": _simular_checkout(frontend_fallback, external_reference),
            "external_checkout_id": f"sim_{external_reference}",
            "external_reference": external_reference,
            "valor": valor,
            "status": "pending",
            "sandbox": True,
        }

    try:
        customer_payload = {
            "name": email_cliente.split("@")[0] if email_cliente else "Cliente DP-IA",
            "email": email_cliente,
        }
        headers = {"access_token": api_key, "Content-Type": "application/json"}
        customer_resp = requests.post(
            f"{base_url}/customers",
            json=customer_payload,
            headers=headers,
            timeout=20,
        )
        customer_resp.raise_for_status()
        customer_id = customer_resp.json().get("id")

        payment_payload = {
            "customer": customer_id,
            "billingType": "UNDEFINED",
            "value": valor,
            "description": f"DP-IA plano {plano}",
            "externalReference": external_reference,
        }
        payment_resp = requests.post(
            f"{base_url}/payments",
            json=payment_payload,
            headers=headers,
            timeout=20,
        )
        payment_resp.raise_for_status()
        payment_data = payment_resp.json()

        checkout_url = (
            payment_data.get("invoiceUrl")
            or payment_data.get("bankSlipUrl")
            or _simular_checkout(frontend_fallback, external_reference)
        )
        return {
            "ok": True,
            "provider": PROVIDER_ASAAS,
            "checkout_url": checkout_url,
            "external_checkout_id": payment_data.get("id"),
            "external_reference": external_reference,
            "valor": valor,
            "status": "pending",
            "sandbox": "sandbox" in base_url,
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": PROVIDER_ASAAS,
            "error": str(exc),
        }


def _gerar_checkout_mercado_pago(plano, email_cliente, valor, external_reference):
    access_token = os.getenv("MP_ACCESS_TOKEN")
    frontend_url = os.getenv("MP_FAKE_CHECKOUT_URL", "https://www.mercadopago.com.br/checkout")

    if not access_token:
        return {
            "ok": True,
            "provider": PROVIDER_MERCADO_PAGO,
            "checkout_url": _simular_checkout(frontend_url, external_reference),
            "external_checkout_id": f"sim_{external_reference}",
            "external_reference": external_reference,
            "valor": valor,
            "status": "pending",
            "sandbox": True,
        }

    try:
        payload = {
            "items": [
                {
                    "title": f"DP-IA Plano {plano}",
                    "quantity": 1,
                    "unit_price": valor,
                    "currency_id": "BRL",
                }
            ],
            "payer": {"email": email_cliente},
            "external_reference": external_reference,
            "auto_return": "approved",
        }
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        resp = requests.post(
            "https://api.mercadopago.com/checkout/preferences",
            json=payload,
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        checkout_url = data.get("init_point") or data.get("sandbox_init_point")

        return {
            "ok": True,
            "provider": PROVIDER_MERCADO_PAGO,
            "checkout_url": checkout_url,
            "external_checkout_id": data.get("id"),
            "external_reference": external_reference,
            "valor": valor,
            "status": "pending",
            "sandbox": bool(data.get("sandbox_init_point")),
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": PROVIDER_MERCADO_PAGO,
            "error": str(exc),
        }


def gerar_external_reference(usuario_id, plano):
    token = uuid.uuid4().hex[:10]
    return f"dpia_{usuario_id}_{plano}_{token}"
