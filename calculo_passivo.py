from config import SALARIO_MINIMO


def calcular_passivo_estimado(dados, salario_usuario=None):

    # =========================
    # 🔥 PRIORIDADE DE SALÁRIO
    # =========================
    if salario_usuario and salario_usuario > 0:
        salario_base = salario_usuario
    elif dados.get("salario") and dados.get("salario") > 0:
        salario_base = dados.get("salario")
    else:
        salario_base = SALARIO_MINIMO

    # =========================
    # 🔥 TEMPO
    # =========================
    meses = dados.get("tempo_empresa_meses")

    if not meses or meses <= 0:
        meses = 12

    semanas = meses * 4.33

    # =========================
    # 🔥 HORAS EXTRAS
    # =========================
    horas_extras_semanais = dados.get("horas_extras_semanais")

    if not horas_extras_semanais or horas_extras_semanais <= 0:
        horas_extras_semanais = 1

    # =========================
    # CÁLCULO
    # =========================
    valor_hora = salario_base / 220
    valor_hora_extra = valor_hora * 1.5

    total_horas = horas_extras_semanais * semanas
    valor_horas = total_horas * valor_hora_extra

    # Reflexos
    fgts = valor_horas * 0.08
    ferias = valor_horas / 3
    decimo_terceiro = valor_horas / 12
    dsr = valor_horas * 0.1667

    total_reflexos = fgts + ferias + decimo_terceiro + dsr
    total = valor_horas + total_reflexos

    # =========================
    # 🔥 CENÁRIO COM PISO
    # =========================
    piso_estimado = salario_base * 1.4
    valor_hora_piso = piso_estimado / 220
    valor_horas_piso = total_horas * valor_hora_piso * 1.5
    total_piso = valor_horas_piso + (valor_horas_piso * 0.6)

    return {
        "salario_base": round(salario_base, 2),
        "meses": meses,
        "semanas": round(semanas, 2),

        "horas_semanais": horas_extras_semanais,

        "valor_hora": round(valor_hora, 2),
        "valor_hora_extra": round(valor_hora_extra, 2),
        "total_horas": round(total_horas, 2),
        "valor_base": round(valor_horas, 2),

        "fgts": round(fgts, 2),
        "ferias": round(ferias, 2),
        "decimo_terceiro": round(decimo_terceiro, 2),
        "dsr": round(dsr, 2),

        "reflexos": round(total_reflexos, 2),
        "total_min": round(total, 2),
        "total_max": round(total_piso, 2)
    }