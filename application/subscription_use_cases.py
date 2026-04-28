from banco import obter_assinatura_usuario, obter_ultimo_checkout_usuario
from plano_service import get_limite_analises, get_limite_empresas, pode_gerar_pdf


def obter_status_assinatura(usuario_id, plano_atual):
    assinatura = obter_assinatura_usuario(usuario_id) or {}
    ultimo_checkout = obter_ultimo_checkout_usuario(usuario_id)

    status_raw = str(assinatura.get("status") or "active").lower()
    status_label = "ativo"

    if status_raw in {"expired", "cancelled", "canceled", "inactive"}:
        status_label = "expirado"
    elif status_raw in {"pending"}:
        status_label = "pendente"

    if ultimo_checkout and str(ultimo_checkout.get("status", "")).lower() in {"pending"}:
        status_label = "aguardando pagamento"

    limite_analises = get_limite_analises(plano_atual)
    limite_empresas = get_limite_empresas(plano_atual)
    pdf_premium = pode_gerar_pdf(plano_atual)

    beneficios = [
        f"Análises/mês: {'Ilimitadas' if limite_analises == float('inf') else int(limite_analises)}",
        f"Empresas: {'Ilimitadas' if limite_empresas == float('inf') else int(limite_empresas)}",
        f"PDF premium: {'Liberado' if pdf_premium else 'Não disponível'}",
        "Prioridade futura: alta" if plano_atual in {"PRO", "PREMIUM"} else "Prioridade futura: padrão",
    ]

    return {
        "plano": plano_atual,
        "status": status_label,
        "next_billing_at": assinatura.get("next_billing_at"),
        "beneficios": beneficios,
        "tem_checkout_pendente": status_label == "aguardando pagamento",
    }
