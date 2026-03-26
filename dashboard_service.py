from banco import get_conexao


def carregar_dados_dashboard():
    conn = get_conexao()
    cursor = conn.cursor()

    cursor.execute("SELECT risco FROM analises")
    dados = cursor.fetchall()

    conn.close()

    riscos = [r[0] for r in dados if r[0]]

    total = len(riscos)

    if total == 0:
        return {
            "total": 0,
            "alto": 0,
            "medio": 0,
            "baixo": 0,
            "percentual_alto": 0,
            "risco_medio": "N/A"
        }

    alto = riscos.count("ALTO")
    medio = riscos.count("MÉDIO")
    baixo = riscos.count("BAIXO")

    percentual_alto = round((alto / total) * 100, 1)

    # score simples
    score = (alto * 3) + (medio * 2) + (baixo * 1)
    media = score / total

    if media >= 2.5:
        risco_medio = "ALTO"
    elif media >= 1.5:
        risco_medio = "MÉDIO"
    else:
        risco_medio = "BAIXO"

    return {
        "total": total,
        "alto": alto,
        "medio": medio,
        "baixo": baixo,
        "percentual_alto": percentual_alto,
        "risco_medio": risco_medio
    }