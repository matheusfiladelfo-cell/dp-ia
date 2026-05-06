"""
Perfis por empresa: admin, gestor, colaborador — seguro por padrão (sem vínculo = sem permissões especiais).
"""

from banco import obter_perfil_na_empresa, usuario_eh_admin


def resolver_perfil_na_empresa(usuario_id, empresa_id) -> str | None:
    """
    Retorna o perfil efetivo para a empresa selecionada.
    Administradores da plataforma (is_admin) são tratados como admin na empresa.
    """
    if not empresa_id or usuario_id is None:
        return None
    if usuario_eh_admin(int(usuario_id)):
        return "admin"
    return obter_perfil_na_empresa(int(usuario_id), int(empresa_id))


def pode_ver_dashboard_corporativo(perfil: str | None) -> bool:
    return perfil in ("admin", "gestor")


def pode_acessar_gestao_equipe(perfil: str | None) -> bool:
    return perfil == "admin"


def pode_gerenciar_integracoes_payroll(perfil: str | None) -> bool:
    """Chaves de API por empresa e instruções de ingestão — apenas administrador da equipe."""
    return perfil == "admin"


def pode_cadastrar_nova_empresa(perfil: str | None) -> bool:
    """Gestores e admins podem criar empresa; colaboradores não."""
    return perfil in ("admin", "gestor")


def filtrar_casos_por_perfil(casos: list, usuario_id, perfil: str | None) -> list:
    """Colaborador enxerga apenas casos criados por si; admin/gestor veem todos."""
    if perfil != "colaborador":
        return list(casos or [])
    uid = int(usuario_id)
    out = []
    for c in casos or []:
        criador = c.get("criado_por_usuario_id")
        try:
            if criador is not None and int(criador) == uid:
                out.append(c)
        except (TypeError, ValueError):
            continue
    return out


def usuario_pode_abrir_caso(caso: dict | None, usuario_id, perfil: str | None) -> bool:
    if not caso:
        return False
    if perfil in ("admin", "gestor"):
        return True
    if perfil != "colaborador":
        return False
    criador = caso.get("criado_por_usuario_id")
    try:
        return criador is not None and int(criador) == int(usuario_id)
    except (TypeError, ValueError):
        return False
