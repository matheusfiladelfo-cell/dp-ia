from application.score_engine_v2 import calcular_score_v2_1


cenario_1 = {
    "tipo_contrato": "PJ",
    "data_admissao": "01/01/2024",
    "data_demissao": "01/05/2024",
    "valor_salario": "4500",
    "motivo_reclamacao": "Verbas rescisórias",
    "evidencias_mencionadas": [],
}

cenario_2 = {
    "tipo_contrato": "PJ",
    "data_admissao": "01/01/2022",
    "data_demissao": "01/05/2024",
    "valor_salario": "7000",
    "cargo": "Gerente de Projetos",
    "motivo_reclamacao": "Reconhecimento de vínculo e pagamento de horas extras",
    "evidencias_mencionadas": [],
}

cenario_3 = {
    "tipo_contrato": "CLT",
    "data_admissao": "10/03/2023",
    "data_demissao": "01/05/2024",
    "valor_salario": "5200",
    "motivo_reclamacao": "Sofri assédio moral por parte da minha liderança.",
    "evidencias_mencionadas": ["e-mails", "gravações de reuniões"],
}


def executar_cenario(fatos: dict) -> dict:
    (
        score_final,
        nivel,
        racional,
        pontuacao_bruta,
        impacto,
        fator_ajuste,
        categoria_fator,
        impacto_md,
    ) = calcular_score_v2_1(fatos)
    return {
        "disponivel": True,
        "score_final": score_final,
        "nivel": nivel,
        "racional": racional,
        "pontuacao_bruta": pontuacao_bruta,
        "impacto_financeiro_estimado": impacto,
        "fator_ajuste_impacto": fator_ajuste,
        "categoria_fator_impacto": categoria_fator,
        "impacto_financeiro_detalhe_md": impacto_md,
    }


def imprimir_resultado(nome_cenario: str, resultado: dict):
    print(f"--- Resultado para: {nome_cenario} ---")
    if not resultado.get("disponivel"):
        print("Score não disponível.")
        print("-" * 40)
        return
    print(
        f"Score Final: {resultado['score_final']}/100 ({resultado['nivel']}) "
        f"| Pontuação bruta: {round(float(resultado.get('pontuacao_bruta') or 0), 2)}"
    )
    print(f"Impacto Potencial Estimado: R$ {float(resultado.get('impacto_financeiro_estimado') or 0):,.2f}")
    print(
        f"Fator de Ajuste Aplicado: {int(round(float(resultado.get('fator_ajuste_impacto') or 0) * 100))}% "
        f"({resultado.get('categoria_fator_impacto')})"
    )
    print("Racional:")
    for linha in resultado.get("racional", []):
        txt = str(linha).replace("→", "->")
        print(f"  - {txt}")
    print("-" * 40)


if __name__ == "__main__":
    resultado_1 = executar_cenario(cenario_1)
    imprimir_resultado("Cenário 1 (Simples)", resultado_1)

    resultado_2 = executar_cenario(cenario_2)
    imprimir_resultado("Cenário 2 (Agravado)", resultado_2)

    resultado_3 = executar_cenario(cenario_3)
    imprimir_resultado("Cenário 3 (Crítico)", resultado_3)
