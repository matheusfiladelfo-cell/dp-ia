from banco import conectar
import json


def obter_memoria_empresa(empresa_id, limite=10):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT risco, tipo_caso, parecer_json
    FROM analises
    WHERE empresa_id = ?
    ORDER BY id DESC
    LIMIT ?
    """, (empresa_id, limite))

    rows = cursor.fetchall()
    conn.close()

    memoria = []

    for r in rows:
        try:
            parecer = json.loads(r[2])
        except:
            parecer = {}

        memoria.append({
            "risco": r[0],
            "tipo": r[1],
            "resumo": parecer.get("diagnostico", "")[:200]
        })

    return memoria


def gerar_contexto_memoria(memoria):
    if not memoria:
        return "Sem histórico relevante."

    texto = "Histórico recente da empresa:\n\n"

    for m in memoria:
        texto += f"- Caso: {m['tipo']} | Risco: {m['risco']}\n"
        texto += f"  {m['resumo']}\n\n"

    return texto