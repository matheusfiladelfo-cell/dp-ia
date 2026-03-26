from banco import conectar
import json


def gerar_relatorio_empresa(empresa_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT risco, tipo_caso, parecer_json
    FROM analises
    WHERE empresa_id = ?
    """, (empresa_id,))

    dados = cursor.fetchall()
    conn.close()

    if not dados:
        return None

    total = len(dados)
    alto = sum(1 for d in dados if d[0] == "ALTO")

    percentual = int((alto / total) * 100)

    problemas = {}
    impacto = 0

    for d in dados:
        tipo = d[1]
        problemas[tipo] = problemas.get(tipo, 0) + 1

        try:
            parecer = json.loads(d[2])
            impacto += parecer.get("impacto_financeiro", 0)
        except:
            pass

    principal = max(problemas, key=problemas.get)

    return {
        "percentual": percentual,
        "problema": principal,
        "impacto": impacto
    }