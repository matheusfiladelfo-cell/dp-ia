def formatar_risco_visual(risco, pontuacao):

    if pontuacao is None:
        return f"⚠ RISCO: {risco}"

    if pontuacao >= 80:
        emoji = "🔴"
    elif pontuacao >= 40:
        emoji = "🟠"
    else:
        emoji = "🟢"

    return f"{emoji} RISCO {risco} ({pontuacao}/100)"