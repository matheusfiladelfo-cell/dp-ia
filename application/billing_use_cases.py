from banco import (
    atualizar_checkout_status,
    criar_checkout_transacao,
    definir_plano_usuario,
    obter_checkout_por_referencia,
    obter_email_usuario,
)
from gateway_pagamento import gerar_checkout_link, gerar_external_reference


PLANOS_PAGOS = {"PRO", "PREMIUM"}


def iniciar_checkout_plano(usuario_id, plano, provider="ASAAS"):
    plano = str(plano).upper()
    if plano not in PLANOS_PAGOS:
        return {"ok": False, "error": "Plano inválido para checkout"}

    email = obter_email_usuario(usuario_id)
    external_reference = gerar_external_reference(usuario_id, plano)
    gateway_resp = gerar_checkout_link(provider, plano, email, external_reference)

    if not gateway_resp.get("ok"):
        return gateway_resp

    criar_checkout_transacao(
        usuario_id=usuario_id,
        plano_destino=plano,
        provider=gateway_resp.get("provider", provider),
        status=gateway_resp.get("status", "pending"),
        checkout_url=gateway_resp.get("checkout_url"),
        external_reference=external_reference,
        external_checkout_id=gateway_resp.get("external_checkout_id"),
        valor=gateway_resp.get("valor", 0.0),
    )
    return gateway_resp


def confirmar_pagamento_checkout(external_reference, status, external_subscription_id=None):
    registro = obter_checkout_por_referencia(external_reference)
    if not registro:
        return {"ok": False, "error": "Transação não encontrada"}

    _id, usuario_id, plano_destino, _provider, _status_atual = registro
    status_norm = str(status or "").lower()
    aprovado = status_norm in {"approved", "paid", "confirmed", "recebido"}

    novo_status = "paid" if aprovado else status_norm or "pending"
    atualizar_checkout_status(
        external_reference=external_reference,
        status=novo_status,
        external_subscription_id=external_subscription_id,
    )

    if aprovado:
        definir_plano_usuario(usuario_id, plano_destino, status="active")
        return {
            "ok": True,
            "updated_plan": plano_destino,
            "usuario_id": usuario_id,
            "status": novo_status,
        }

    return {"ok": True, "status": novo_status, "usuario_id": usuario_id}
