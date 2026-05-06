from datetime import datetime, timedelta

import pandas as pd

from banco import conectar


def _calc_delta_percent(valor_atual: int, valor_anterior: int) -> float:
    atual = int(valor_atual or 0)
    anterior = int(valor_anterior or 0)
    if anterior == 0:
        return 1.0 if atual > 0 else 0.0
    return (atual - anterior) / float(anterior)


def _period_bounds(periodo_dias: int) -> dict:
    dias = max(1, int(periodo_dias or 30))
    hoje = datetime.now()
    atual_inicio_dt = hoje - timedelta(days=dias - 1)
    atual_fim_dt = hoje
    anterior_inicio_dt = hoje - timedelta(days=(2 * dias) - 1)
    anterior_fim_dt = hoje - timedelta(days=dias)
    return {
        "atual_inicio": atual_inicio_dt.strftime("%Y-%m-%d"),
        "atual_fim": atual_fim_dt.strftime("%Y-%m-%d"),
        "anterior_inicio": anterior_inicio_dt.strftime("%Y-%m-%d"),
        "anterior_fim": anterior_fim_dt.strftime("%Y-%m-%d"),
        "label_atual": f"{atual_inicio_dt.strftime('%d/%m/%Y')} a {atual_fim_dt.strftime('%d/%m/%Y')}",
        "label_anterior": f"{anterior_inicio_dt.strftime('%d/%m/%Y')} a {anterior_fim_dt.strftime('%d/%m/%Y')}",
    }


def obter_labels_periodo(periodo_dias=30) -> dict:
    bounds = _period_bounds(periodo_dias)
    return {
        "label_atual": bounds["label_atual"],
        "label_anterior": bounds["label_anterior"],
    }


def calcular_kpis_principais(periodo_dias=30) -> dict:
    conn = conectar()
    cursor = conn.cursor()
    bounds = _period_bounds(periodo_dias)
    inicio_atual = bounds["atual_inicio"]
    inicio_anterior = bounds["anterior_inicio"]
    fim_anterior = bounds["anterior_fim"]

    cursor.execute(
        """
        SELECT COUNT(*) FROM usuarios u
        LEFT JOIN assinaturas a ON a.usuario_id = u.id
        WHERE COALESCE(u.bloqueado, 0) = 0
          AND LOWER(COALESCE(a.status, 'active')) <> 'suspended'
          AND date(COALESCE(a.created_at, '')) >= date(?)
        """
        ,
        (inicio_atual,),
    )
    usuarios_ativos_atual = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM usuarios u
        LEFT JOIN assinaturas a ON a.usuario_id = u.id
        WHERE COALESCE(u.bloqueado, 0) = 0
          AND LOWER(COALESCE(a.status, 'active')) <> 'suspended'
          AND date(COALESCE(a.created_at, '')) >= date(?)
          AND date(COALESCE(a.created_at, '')) <= date(?)
        """,
        (inicio_anterior, fim_anterior),
    )
    usuarios_ativos_anterior = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM empresas
        WHERE date(COALESCE(data_cadastro, '')) >= date(?)
        """,
        (inicio_atual,),
    )
    empresas_atual = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM empresas
        WHERE date(COALESCE(data_cadastro, '')) >= date(?)
          AND date(COALESCE(data_cadastro, '')) <= date(?)
        """,
        (inicio_anterior, fim_anterior),
    )
    empresas_anterior = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM analises
        WHERE date(COALESCE(data_analise, '')) >= date(?)
        """,
        (inicio_atual,),
    )
    analises_atual = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM analises
        WHERE date(COALESCE(data_analise, '')) >= date(?)
          AND date(COALESCE(data_analise, '')) <= date(?)
        """,
        (inicio_anterior, fim_anterior),
    )
    analises_anterior = int(cursor.fetchone()[0] or 0)

    conn.close()
    return {
        "total_usuarios_ativos": {
            "value": usuarios_ativos_atual,
            "delta": _calc_delta_percent(usuarios_ativos_atual, usuarios_ativos_anterior),
        },
        "total_empresas": {
            "value": empresas_atual,
            "delta": _calc_delta_percent(empresas_atual, empresas_anterior),
        },
        "total_analises_periodo": {
            "value": analises_atual,
            "delta": _calc_delta_percent(analises_atual, analises_anterior),
        },
    }


def obter_dados_crescimento_usuarios_por_dia(periodo_dias=30) -> list[dict]:
    dias = max(1, int(periodo_dias or 30))
    bounds = _period_bounds(dias)
    inicio_atual = bounds["atual_inicio"]
    inicio_anterior = bounds["anterior_inicio"]
    fim_anterior = bounds["anterior_fim"]
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            date(COALESCE(a.created_at, '')) AS dia,
            COUNT(*) AS total
        FROM usuarios u
        LEFT JOIN assinaturas a ON a.usuario_id = u.id
        WHERE date(COALESCE(a.created_at, '')) >= date(?)
          AND date(COALESCE(a.created_at, '')) <= date('now')
        GROUP BY date(COALESCE(a.created_at, ''))
        ORDER BY dia ASC
        """,
        (inicio_atual,),
    )
    rows_atual = cursor.fetchall()
    cursor.execute(
        """
        SELECT
            date(COALESCE(a.created_at, '')) AS dia,
            COUNT(*) AS total
        FROM usuarios u
        LEFT JOIN assinaturas a ON a.usuario_id = u.id
        WHERE date(COALESCE(a.created_at, '')) >= date(?)
          AND date(COALESCE(a.created_at, '')) <= date(?)
        GROUP BY date(COALESCE(a.created_at, ''))
        ORDER BY dia ASC
        """,
        (inicio_anterior, fim_anterior),
    )
    rows_anterior = cursor.fetchall()
    conn.close()
    base_atual = datetime.strptime(inicio_atual, "%Y-%m-%d")
    base_anterior = datetime.strptime(inicio_anterior, "%Y-%m-%d")
    serie_atual = {i: 0 for i in range(1, dias + 1)}
    serie_anterior = {i: 0 for i in range(1, dias + 1)}

    for dia_txt, total in rows_atual:
        if not dia_txt:
            continue
        idx = (datetime.strptime(str(dia_txt), "%Y-%m-%d") - base_atual).days + 1
        if 1 <= idx <= dias:
            serie_atual[idx] = int(total or 0)
    for dia_txt, total in rows_anterior:
        if not dia_txt:
            continue
        idx = (datetime.strptime(str(dia_txt), "%Y-%m-%d") - base_anterior).days + 1
        if 1 <= idx <= dias:
            serie_anterior[idx] = int(total or 0)

    index = [f"Dia {i}" for i in range(1, dias + 1)]
    return pd.DataFrame(
        {
            "Período Atual": [serie_atual[i] for i in range(1, dias + 1)],
            "Período Anterior": [serie_anterior[i] for i in range(1, dias + 1)],
        },
        index=index,
    )


def obter_distribuicao_planos() -> list[dict]:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT UPPER(COALESCE(plano, 'FREE')) AS plano, COUNT(*) AS total
        FROM assinaturas
        GROUP BY UPPER(COALESCE(plano, 'FREE'))
        ORDER BY total DESC, plano ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"plano": str(r[0] or "FREE"), "total": int(r[1] or 0)} for r in rows]


def obter_distribuicao_eventos_produto(periodo_dias=30) -> pd.DataFrame:
    dias = max(1, int(periodo_dias or 30))
    bounds = _period_bounds(dias)
    inicio_atual = bounds["atual_inicio"]
    inicio_anterior = bounds["anterior_inicio"]
    fim_anterior = bounds["anterior_fim"]
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date(COALESCE(timestamp_evento, '')) AS dia, COUNT(*) AS total
        FROM eventos_produto
        WHERE date(COALESCE(timestamp_evento, '')) >= date(?)
          AND date(COALESCE(timestamp_evento, '')) <= date('now')
        GROUP BY date(COALESCE(timestamp_evento, ''))
        ORDER BY dia ASC
        """,
        (inicio_atual,),
    )
    rows_atual = cursor.fetchall()
    cursor.execute(
        """
        SELECT date(COALESCE(timestamp_evento, '')) AS dia, COUNT(*) AS total
        FROM eventos_produto
        WHERE date(COALESCE(timestamp_evento, '')) >= date(?)
          AND date(COALESCE(timestamp_evento, '')) <= date(?)
        GROUP BY date(COALESCE(timestamp_evento, ''))
        ORDER BY dia ASC
        """,
        (inicio_anterior, fim_anterior),
    )
    rows_anterior = cursor.fetchall()
    conn.close()

    base_atual = datetime.strptime(inicio_atual, "%Y-%m-%d")
    base_anterior = datetime.strptime(inicio_anterior, "%Y-%m-%d")
    serie_atual = {i: 0 for i in range(1, dias + 1)}
    serie_anterior = {i: 0 for i in range(1, dias + 1)}

    for dia_txt, total in rows_atual:
        if not dia_txt:
            continue
        idx = (datetime.strptime(str(dia_txt), "%Y-%m-%d") - base_atual).days + 1
        if 1 <= idx <= dias:
            serie_atual[idx] = int(total or 0)
    for dia_txt, total in rows_anterior:
        if not dia_txt:
            continue
        idx = (datetime.strptime(str(dia_txt), "%Y-%m-%d") - base_anterior).days + 1
        if 1 <= idx <= dias:
            serie_anterior[idx] = int(total or 0)

    index = [f"Dia {i}" for i in range(1, dias + 1)]
    return pd.DataFrame(
        {
            "Período Atual": [serie_atual[i] for i in range(1, dias + 1)],
            "Período Anterior": [serie_anterior[i] for i in range(1, dias + 1)],
        },
        index=index,
    )


def obter_distribuicao_eventos_produto_por_nome(periodo_dias=30) -> list[dict]:
    conn = conectar()
    cursor = conn.cursor()
    bounds = _period_bounds(periodo_dias)
    inicio = bounds["atual_inicio"]
    cursor.execute(
        """
        SELECT COALESCE(nome_evento, 'evento_indefinido') AS nome_evento, COUNT(*) AS total
        FROM eventos_produto
        WHERE date(COALESCE(timestamp_evento, '')) >= date(?)
        GROUP BY COALESCE(nome_evento, 'evento_indefinido')
        ORDER BY total DESC, nome_evento ASC
        """,
        (inicio,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"nome_evento": str(r[0] or ""), "total": int(r[1] or 0)} for r in rows]
