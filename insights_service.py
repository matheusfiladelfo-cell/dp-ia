from banco import TIPO_ANALISE_STUB_VALIDACAO_FATOS, conectar


def gerar_insights_empresa(empresa_id, criado_por_usuario_id=None):
    conn = conectar()
    cursor = conn.cursor()

    if criado_por_usuario_id is not None:
        cursor.execute(
            """
            SELECT risco, tipo_caso FROM analises
            WHERE empresa_id = ?
              AND COALESCE(criado_por_usuario_id, -1) = ?
              AND COALESCE(tipo_caso, '') != ?
            """,
            (empresa_id, int(criado_por_usuario_id), TIPO_ANALISE_STUB_VALIDACAO_FATOS),
        )
    else:
        cursor.execute(
            """
            SELECT risco, tipo_caso FROM analises
            WHERE empresa_id = ?
              AND COALESCE(tipo_caso, '') != ?
            """,
            (empresa_id, TIPO_ANALISE_STUB_VALIDACAO_FATOS),
        )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None

    total = len(rows)

    alto = sum(1 for r in rows if r[0] == "ALTO")
    medio = sum(1 for r in rows if r[0] == "MÉDIO")

    percentual_alto = int((alto / total) * 100)

    # problema mais comum
    tipos = {}
    for r in rows:
        tipos[r[1]] = tipos.get(r[1], 0) + 1

    problema_principal = max(tipos, key=tipos.get)

    return {
        "total": total,
        "percentual_alto": percentual_alto,
        "problema": problema_principal
    }