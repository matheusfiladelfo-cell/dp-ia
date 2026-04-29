import csv
import os
import sqlite3
import time
from datetime import datetime
import json
import bcrypt

LEADS_CSV_FALLBACK = "leads.csv"

# CRM / funil comercial (leads)
LEAD_CRM_STATUSES = (
    "novo",
    "contato_feito",
    "demo_agendada",
    "proposta_enviada",
    "cliente_fechado",
    "perdido",
    "pausado",
)

# 🔥 PADRÃO ÚNICO DE BANCO (CRÍTICO)
DB_NAME = "dpia.db"
_LOGIN_MAX_FAILED = 5
_LOGIN_WINDOW_SECONDS = 10 * 60
_LOGIN_BLOCK_SECONDS = 3 * 60


def _admin_master_email() -> str | None:
    raw = os.environ.get("ADMIN_MASTER_EMAIL")
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip().lower()


def _email_admin_master(email: str | None) -> bool:
    master = _admin_master_email()
    if not email or not master:
        return False
    return str(email).strip().lower() == master


def _login_key(email: str | None, ip: str | None = None) -> str:
    e = (email or "").strip().lower()
    i = (ip or "").strip().lower() or "noip"
    return f"{e}|{i}"


def _login_rate_limit_gc(cursor, now_ts: float) -> None:
    cutoff = now_ts - (_LOGIN_WINDOW_SECONDS * 2)
    cursor.execute(
        """
        DELETE FROM login_rate_limit
        WHERE COALESCE(blocked_until_ts, 0) < ? AND COALESCE(last_fail_ts, 0) < ?
        """,
        (now_ts, cutoff),
    )


def verificar_rate_limit_login(email: str | None, ip: str | None = None) -> tuple[bool, int]:
    """
    Retorna (permitido, segundos_restantes_bloqueio).
    Bloqueio leve persistente para reduzir força bruta entre reinícios.
    """
    key = _login_key(email, ip)
    now_ts = time.time()
    conn = conectar()
    cursor = conn.cursor()
    _login_rate_limit_gc(cursor, now_ts)
    cursor.execute(
        """
        SELECT COALESCE(blocked_until_ts, 0)
        FROM login_rate_limit
        WHERE rl_key = ?
        """,
        (key,),
    )
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    if not row:
        return True, 0
    blocked_until = float(row[0] or 0.0)
    if blocked_until > now_ts:
        return False, int(blocked_until - now_ts)
    return True, 0


def registrar_falha_login(email: str | None, ip: str | None = None) -> None:
    key = _login_key(email, ip)
    now_ts = time.time()
    conn = conectar()
    cursor = conn.cursor()
    _login_rate_limit_gc(cursor, now_ts)
    cursor.execute(
        """
        SELECT COALESCE(failed_count, 0), COALESCE(first_fail_ts, 0), COALESCE(blocked_until_ts, 0)
        FROM login_rate_limit
        WHERE rl_key = ?
        """,
        (key,),
    )
    row = cursor.fetchone()
    if not row:
        failed_count = 1
        first_fail = now_ts
        blocked_until = 0.0
    else:
        failed_count = int(row[0] or 0)
        first_fail = float(row[1] or now_ts)
        blocked_until = float(row[2] or 0.0)
        if (now_ts - first_fail) > _LOGIN_WINDOW_SECONDS:
            failed_count = 0
            first_fail = now_ts
        if blocked_until > now_ts:
            conn.commit()
            conn.close()
            return
        failed_count += 1
    if failed_count >= _LOGIN_MAX_FAILED:
        blocked_until = now_ts + _LOGIN_BLOCK_SECONDS
        failed_count = 0
        first_fail = now_ts
    cursor.execute(
        """
        INSERT OR REPLACE INTO login_rate_limit (
            rl_key, failed_count, first_fail_ts, last_fail_ts, blocked_until_ts, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (key, failed_count, first_fail, now_ts, blocked_until, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def resetar_falhas_login(email: str | None, ip: str | None = None) -> None:
    """
    Se ip for informado, limpa só a chave daquele par email/ip.
    Se ip for None, limpa todas as chaves do email.
    """
    e = (email or "").strip().lower()
    if not e:
        return
    conn = conectar()
    cursor = conn.cursor()
    if ip is not None:
        cursor.execute(
            "DELETE FROM login_rate_limit WHERE rl_key = ?",
            (_login_key(email, ip),),
        )
    else:
        cursor.execute(
            "DELETE FROM login_rate_limit WHERE rl_key LIKE ?",
            (f"{e}|%",),
        )
    conn.commit()
    conn.close()


# =========================
# CONEXÃO CENTRALIZADA
# =========================
def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def _garantir_coluna_usuarios_bloqueado():
    """Migração leve: bloqueio administrativo (0 = liberado, 1 = bloqueado)."""
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN bloqueado INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _garantir_coluna_usuarios_is_admin():
    """Migração leve: flag de privilégio admin (0 = comum, 1 = admin)."""
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "ALTER TABLE usuarios ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _bootstrap_admin_master():
    """
    Bootstrap opcional via ADMIN_MASTER_EMAIL:
    se definida, garante somente este usuário com is_admin=1.
    """
    master = _admin_master_email()
    if not master:
        return
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE usuarios
        SET is_admin = CASE
            WHEN LOWER(COALESCE(email, '')) = ? THEN 1
            ELSE 0
        END
        """
        ,
        (master,),
    )
    conn.commit()
    conn.close()


# =========================
# TABELAS
# =========================
def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        senha_hash TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS uso_mensal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        mes TEXT,
        total_analises INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS empresas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        nome TEXT,
        cnpj TEXT,
        cidade TEXT,
        estado TEXT,
        data_cadastro TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER,
        data_analise TEXT,
        tipo_caso TEXT,
        risco TEXT,
        pontuacao INTEGER,
        dados_json TEXT,
        resultado_json TEXT,
        parecer_json TEXT,
        versao_ia TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assinaturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER UNIQUE,
        plano TEXT DEFAULT 'FREE',
        status TEXT DEFAULT 'active',
        billing_cycle TEXT DEFAULT 'monthly',
        payment_provider TEXT,
        external_customer_id TEXT,
        external_subscription_id TEXT,
        next_billing_at TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS checkout_transacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        plano_destino TEXT,
        provider TEXT,
        status TEXT,
        checkout_url TEXT,
        external_reference TEXT UNIQUE,
        external_checkout_id TEXT,
        external_subscription_id TEXT,
        valor REAL,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS onboarding_usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER UNIQUE,
        etapa_atual INTEGER DEFAULT 1,
        concluido INTEGER DEFAULT 0,
        criado_em TEXT,
        atualizado_em TEXT,
        concluido_em TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback_resultado_analise (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        empresa_id INTEGER,
        ajudou INTEGER,
        risco_coerente INTEGER,
        recomendacao_util INTEGER,
        nota_geral INTEGER,
        score INTEGER,
        nivel TEXT,
        parecer_schema_version TEXT,
        observacoes TEXT,
        criado_em TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        empresa TEXT,
        whatsapp TEXT,
        email TEXT,
        plano_interesse TEXT,
        criado_em TEXT NOT NULL,
        origem TEXT DEFAULT 'landing'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS login_rate_limit (
        rl_key TEXT PRIMARY KEY,
        failed_count INTEGER DEFAULT 0,
        first_fail_ts REAL,
        last_fail_ts REAL,
        blocked_until_ts REAL DEFAULT 0,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_user_id INTEGER,
        action TEXT NOT NULL,
        target_type TEXT,
        target_id TEXT,
        details TEXT,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()
    _garantir_coluna_usuarios_bloqueado()
    _garantir_coluna_usuarios_is_admin()
    _garantir_colunas_leads_crm()
    _bootstrap_admin_master()


def _garantir_colunas_leads_crm():
    conn = conectar()
    cursor = conn.cursor()
    for stmt in (
        "ALTER TABLE leads ADD COLUMN status TEXT DEFAULT 'novo'",
        "ALTER TABLE leads ADD COLUMN observacoes TEXT DEFAULT ''",
        "ALTER TABLE leads ADD COLUMN atualizado_em TEXT",
    ):
        try:
            cursor.execute(stmt)
            conn.commit()
        except sqlite3.OperationalError:
            pass
    cursor.execute(
        """
        UPDATE leads SET atualizado_em = criado_em
        WHERE atualizado_em IS NULL OR TRIM(atualizado_em) = ''
        """
    )
    cursor.execute(
        """
        UPDATE leads SET status = 'novo'
        WHERE status IS NULL OR TRIM(status) = ''
        """
    )
    conn.commit()
    conn.close()


def _append_lead_csv_fallback(row):
    """row: nome, empresa, whatsapp, email, plano_interesse, criado_em, origem"""
    path = LEADS_CSV_FALLBACK
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(
                [
                    "nome",
                    "empresa",
                    "whatsapp",
                    "email",
                    "plano_interesse",
                    "criado_em",
                    "origem",
                ]
            )
        w.writerow(row)


def salvar_lead_demonstracao(nome, empresa, whatsapp, email, plano_interesse):
    """
    Grava lead na tabela leads. Se o banco falhar, tenta append em leads.csv.
    Retorna (sucesso, detalhe): detalhe é 'db', 'csv_fallback' ou mensagem de erro.
    """
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nome = (nome or "").strip()
    empresa = (empresa or "").strip()
    whatsapp = (whatsapp or "").strip()
    email = (email or "").strip()
    plano_interesse = (plano_interesse or "").strip()
    origem = "landing"

    row = (nome, empresa, whatsapp, email, plano_interesse, agora, origem)

    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO leads (
                nome, empresa, whatsapp, email, plano_interesse, criado_em, origem,
                status, observacoes, atualizado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'novo', '', ?)
            """,
            (*row, agora),
        )
        conn.commit()
        conn.close()
        return True, "db"
    except Exception:
        try:
            _append_lead_csv_fallback(row)
            return True, "csv_fallback"
        except Exception as exc:
            return False, str(exc)


# =========================
# 🔐 USUÁRIOS
# =========================
def criar_usuario(email, senha):
    conn = conectar()
    cursor = conn.cursor()

    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())

    cursor.execute("""
    INSERT INTO usuarios (email, senha_hash)
    VALUES (?, ?)
    """, (email, senha_hash))

    usuario_id = cursor.lastrowid
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT OR IGNORE INTO assinaturas (
        usuario_id,
        plano,
        status,
        billing_cycle,
        created_at,
        updated_at
    )
    VALUES (?, 'FREE', 'active', 'monthly', ?, ?)
    """, (usuario_id, agora, agora))

    cursor.execute("""
    INSERT OR IGNORE INTO onboarding_usuario (
        usuario_id,
        etapa_atual,
        concluido,
        criado_em,
        atualizado_em
    )
    VALUES (?, 1, 0, ?, ?)
    """, (usuario_id, agora, agora))

    conn.commit()
    conn.close()


def login_usuario(email, senha):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT u.id, u.senha_hash, COALESCE(u.bloqueado, 0),
               LOWER(COALESCE(a.status, 'active'))
        FROM usuarios u
        LEFT JOIN assinaturas a ON a.usuario_id = u.id
        WHERE u.email = ?
        """,
        (email,),
    )

    user = cursor.fetchone()
    conn.close()

    if not user:
        return None

    user_id, senha_hash, bloqueado, status_assin = user

    master_ok = _email_admin_master(email)

    if int(bloqueado or 0) == 1 and not master_ok:
        return None
    if status_assin == "suspended" and not master_ok:
        return None

    if bcrypt.checkpw(senha.encode(), senha_hash):
        promover_admin_por_email_se_necessario(user_id, email)
        resetar_falhas_login(email)
        return user_id

    return None


def obter_email_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def usuario_eh_admin(usuario_id) -> bool:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(is_admin, 0) FROM usuarios WHERE id = ?",
        (usuario_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return bool(row and int(row[0] or 0) == 1)


def promover_admin_por_email_se_necessario(usuario_id, email: str | None) -> None:
    """
    Se ADMIN_MASTER_EMAIL estiver configurado e o login corresponder,
    garante is_admin=1 para restaurar acesso admin sem intervenção manual.
    """
    if not _email_admin_master(email):
        return
    if usuario_eh_admin(usuario_id):
        return
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET is_admin = 1 WHERE id = ?",
        (int(usuario_id),),
    )
    conn.commit()
    conn.close()


def registrar_admin_audit(
    admin_user_id,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: str | None = None,
):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO admin_audit_log (
            admin_user_id, action, target_type, target_id, details, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(admin_user_id) if admin_user_id is not None else None,
            str(action or "").strip() or "admin_action",
            str(target_type or "").strip() or None,
            str(target_id or "").strip() or None,
            str(details or "").strip() or None,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()


# =========================
# USO
# =========================
def obter_mes_atual():
    return datetime.now().strftime("%Y-%m")


def obter_uso_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()

    mes = obter_mes_atual()

    cursor.execute("""
    SELECT total_analises FROM uso_mensal
    WHERE usuario_id = ? AND mes = ?
    """, (usuario_id, mes))

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else 0


def incrementar_uso(usuario_id):
    conn = conectar()
    cursor = conn.cursor()

    mes = obter_mes_atual()

    cursor.execute("""
    SELECT id FROM uso_mensal
    WHERE usuario_id = ? AND mes = ?
    """, (usuario_id, mes))

    row = cursor.fetchone()

    if row:
        cursor.execute("""
        UPDATE uso_mensal
        SET total_analises = total_analises + 1
        WHERE id = ?
        """, (row[0],))
    else:
        cursor.execute("""
        INSERT INTO uso_mensal (usuario_id, mes, total_analises)
        VALUES (?, ?, 1)
        """, (usuario_id, mes))

    conn.commit()
    conn.close()


# =========================
# EMPRESAS
# =========================
def cadastrar_empresa(usuario_id, nome, cnpj, cidade, estado):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO empresas (usuario_id, nome, cnpj, cidade, estado, data_cadastro)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        usuario_id,
        nome,
        cnpj,
        cidade,
        estado,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def listar_empresas(usuario_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, nome FROM empresas
    WHERE usuario_id = ?
    ORDER BY nome ASC
    """, (usuario_id,))

    dados = cursor.fetchall()
    conn.close()
    return dados


def contar_empresas_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM empresas WHERE usuario_id = ?", (usuario_id,))
    total = cursor.fetchone()[0]
    conn.close()
    return total


def obter_plano_usuario_db(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT plano FROM assinaturas WHERE usuario_id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def garantir_plano_usuario(usuario_id, plano_default="FREE"):
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT OR IGNORE INTO assinaturas (
        usuario_id,
        plano,
        status,
        billing_cycle,
        created_at,
        updated_at
    )
    VALUES (?, ?, 'active', 'monthly', ?, ?)
    """, (usuario_id, plano_default, agora, agora))

    conn.commit()
    conn.close()


def definir_plano_usuario(usuario_id, plano, status="active"):
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    garantir_plano_usuario(usuario_id, plano_default=plano)

    cursor.execute("""
    UPDATE assinaturas
    SET plano = ?, status = ?, updated_at = ?
    WHERE usuario_id = ?
    """, (plano, status, agora, usuario_id))

    conn.commit()
    conn.close()


def criar_checkout_transacao(
    usuario_id,
    plano_destino,
    provider,
    status,
    checkout_url,
    external_reference,
    external_checkout_id=None,
    external_subscription_id=None,
    valor=0.0,
):
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO checkout_transacoes (
        usuario_id,
        plano_destino,
        provider,
        status,
        checkout_url,
        external_reference,
        external_checkout_id,
        external_subscription_id,
        valor,
        created_at,
        updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        usuario_id,
        plano_destino,
        provider,
        status,
        checkout_url,
        external_reference,
        external_checkout_id,
        external_subscription_id,
        valor,
        agora,
        agora,
    ))

    conn.commit()
    conn.close()


def obter_checkout_por_referencia(external_reference):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, usuario_id, plano_destino, provider, status
    FROM checkout_transacoes
    WHERE external_reference = ?
    """, (external_reference,))
    row = cursor.fetchone()
    conn.close()
    return row


def atualizar_checkout_status(
    external_reference,
    status,
    external_subscription_id=None,
):
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE checkout_transacoes
    SET status = ?,
        external_subscription_id = COALESCE(?, external_subscription_id),
        updated_at = ?
    WHERE external_reference = ?
    """, (status, external_subscription_id, agora, external_reference))

    conn.commit()
    conn.close()


def obter_assinatura_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT plano, status, next_billing_at
    FROM assinaturas
    WHERE usuario_id = ?
    """, (usuario_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "plano": row[0],
        "status": row[1],
        "next_billing_at": row[2],
    }


def obter_ultimo_checkout_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT plano_destino, status, created_at
    FROM checkout_transacoes
    WHERE usuario_id = ?
    ORDER BY id DESC
    LIMIT 1
    """, (usuario_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "plano_destino": row[0],
        "status": row[1],
        "created_at": row[2],
    }


def obter_onboarding_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT etapa_atual, concluido, concluido_em
    FROM onboarding_usuario
    WHERE usuario_id = ?
    """, (usuario_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "etapa_atual": int(row[0] or 1),
        "concluido": bool(row[1]),
        "concluido_em": row[2],
    }


def garantir_onboarding_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT OR IGNORE INTO onboarding_usuario (
        usuario_id,
        etapa_atual,
        concluido,
        criado_em,
        atualizado_em
    )
    VALUES (?, 1, 0, ?, ?)
    """, (usuario_id, agora, agora))
    conn.commit()
    conn.close()


def atualizar_onboarding_etapa(usuario_id, etapa_atual):
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    UPDATE onboarding_usuario
    SET etapa_atual = ?, atualizado_em = ?
    WHERE usuario_id = ? AND concluido = 0
    """, (int(etapa_atual), agora, usuario_id))
    conn.commit()
    conn.close()


def concluir_onboarding_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    UPDATE onboarding_usuario
    SET etapa_atual = 3,
        concluido = 1,
        atualizado_em = ?,
        concluido_em = ?
    WHERE usuario_id = ?
    """, (agora, agora, usuario_id))
    conn.commit()
    conn.close()


# =========================
# ANALISES
# =========================
def salvar_analise(
    empresa_id,
    tipo_caso,
    risco,
    pontuacao,
    dados,
    resultado,
    parecer,
    versao_ia="v1"
):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO analises (
        empresa_id,
        data_analise,
        tipo_caso,
        risco,
        pontuacao,
        dados_json,
        resultado_json,
        parecer_json,
        versao_ia
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        empresa_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tipo_caso,
        risco,
        pontuacao,
        json.dumps(dados),
        json.dumps(resultado),
        json.dumps(parecer),
        versao_ia
    ))

    conn.commit()
    conn.close()


def salvar_feedback_resultado_analise(
    usuario_id,
    empresa_id,
    ajudou,
    risco_coerente,
    recomendacao_util,
    nota_geral,
    score=None,
    nivel=None,
    parecer_schema_version=None,
    observacoes="",
):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO feedback_resultado_analise (
            usuario_id,
            empresa_id,
            ajudou,
            risco_coerente,
            recomendacao_util,
            nota_geral,
            score,
            nivel,
            parecer_schema_version,
            observacoes,
            criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            usuario_id,
            empresa_id,
            int(bool(ajudou)),
            int(bool(risco_coerente)),
            int(bool(recomendacao_util)),
            int(nota_geral),
            score,
            nivel,
            parecer_schema_version,
            observacoes,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()


# =========================
# ADMIN (somente leitura / export)
# =========================
def admin_count_usuarios():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    n = cursor.fetchone()[0]
    conn.close()
    return int(n or 0)


def admin_count_leads():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM leads")
    n = cursor.fetchone()[0]
    conn.close()
    return int(n or 0)


def admin_count_analises():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM analises")
    n = cursor.fetchone()[0]
    conn.close()
    return int(n or 0)


def admin_count_usuarios_ativos_7d():
    """Usuários com pelo menos uma análise nos últimos 7 dias (via empresa)."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(DISTINCT e.usuario_id)
        FROM analises a
        INNER JOIN empresas e ON e.id = a.empresa_id
        WHERE date(a.data_analise) >= date('now', '-7 days')
        """
    )
    n = cursor.fetchone()[0]
    conn.close()
    return int(n or 0)


def admin_receita_estimada_mensal_brl():
    """
    Soma simples: assinaturas ativas × preço de catálogo (R$).
    PRO = 197, PREMIUM = 397, FREE = 0 (planejamento / SaaS).
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT UPPER(COALESCE(plano, 'FREE')), COUNT(*)
        FROM assinaturas
        WHERE COALESCE(status, 'active') = 'active'
        GROUP BY UPPER(COALESCE(plano, 'FREE'))
        """
    )
    rows = cursor.fetchall()
    conn.close()
    pricing = {"FREE": 0.0, "PRO": 197.0, "PREMIUM": 397.0}
    total = 0.0
    for plano, cnt in rows:
        key = str(plano or "FREE").upper()
        price = float(pricing.get(key, 0.0))
        total += price * int(cnt or 0)
    return round(total, 2)


def admin_ultimos_usuarios(limit=20):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.id, u.email,
               COALESCE(
                   (SELECT MIN(created_at) FROM assinaturas WHERE usuario_id = u.id),
                   ''
               ) AS cadastro_ref
        FROM usuarios u
        ORDER BY u.id DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_ultimos_leads(limit=20):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, nome, empresa, email, whatsapp, plano_interesse, criado_em,
               COALESCE(status, 'novo')
        FROM leads
        ORDER BY datetime(criado_em) DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_crm_listar_leads(filtro_status: str | None = None):
    """Lista leads para CRM; filtro_status em LEAD_CRM_STATUSES ou None = todos."""
    conn = conectar()
    cursor = conn.cursor()
    base = """
        SELECT id, nome, empresa, whatsapp, email, plano_interesse, criado_em, origem,
               COALESCE(status, 'novo'), COALESCE(observacoes, '')
        FROM leads
    """
    if filtro_status and filtro_status in LEAD_CRM_STATUSES:
        cursor.execute(
            base + " WHERE COALESCE(status, 'novo') = ? ORDER BY datetime(COALESCE(atualizado_em, criado_em)) DESC",
            (filtro_status,),
        )
    else:
        cursor.execute(
            base + " ORDER BY datetime(COALESCE(atualizado_em, criado_em)) DESC"
        )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_crm_atualizar_lead(lead_id, status=None, observacoes=None, actor_admin_id=None):
    """Atualiza status e/ou observações do lead (CRM)."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status is None and observacoes is None:
        return False
    conn = conectar()
    cursor = conn.cursor()
    parts = ["atualizado_em = ?"]
    vals = [agora]
    if status is not None:
        st = str(status).strip().lower()
        if st not in LEAD_CRM_STATUSES:
            st = "novo"
        parts.append("status = ?")
        vals.append(st)
    if observacoes is not None:
        parts.append("observacoes = ?")
        vals.append(str(observacoes))
    vals.append(int(lead_id))
    sql = f"UPDATE leads SET {', '.join(parts)} WHERE id = ?"
    cursor.execute(sql, vals)
    conn.commit()
    conn.close()
    registrar_admin_audit(
        admin_user_id=actor_admin_id,
        action="crm_update_lead",
        target_type="lead",
        target_id=str(lead_id),
        details=f"status={status if status is not None else '-'}",
    )
    return True


def admin_crm_kpis():
    """KPIs do funil comercial (leads)."""
    conn = conectar()
    cursor = conn.cursor()
    ym = datetime.now().strftime("%Y-%m")

    cursor.execute(
        "SELECT COUNT(*) FROM leads WHERE date(criado_em) = date('now')"
    )
    novos_hoje = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM leads
        WHERE COALESCE(status, 'novo') IN (
            'novo', 'contato_feito', 'demo_agendada', 'proposta_enviada'
        )
        """
    )
    em_aberto = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM leads WHERE COALESCE(status, 'novo') = 'demo_agendada'
        """
    )
    demos_marcadas = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM leads
        WHERE status = 'cliente_fechado'
          AND strftime('%Y-%m', COALESCE(atualizado_em, criado_em)) = ?
        """,
        (ym,),
    )
    fechados_mes = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM leads
        WHERE status = 'perdido'
          AND strftime('%Y-%m', COALESCE(atualizado_em, criado_em)) = ?
        """,
        (ym,),
    )
    perdidos_mes = int(cursor.fetchone()[0] or 0)

    conn.close()

    decididos = fechados_mes + perdidos_mes
    taxa_conv = (
        round(100.0 * fechados_mes / decididos, 1) if decididos > 0 else 0.0
    )

    return {
        "novos_hoje": novos_hoje,
        "em_aberto": em_aberto,
        "demos_marcadas": demos_marcadas,
        "fechados_mes": fechados_mes,
        "perdidos_mes": perdidos_mes,
        "taxa_conversao": taxa_conv,
    }


def admin_series_cadastros_30_dias():
    """Contagem por dia (assinaturas.created_at) nos últimos 30 dias."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date(created_at) AS d, COUNT(*)
        FROM assinaturas
        WHERE created_at IS NOT NULL
          AND date(created_at) >= date('now', '-30 days')
        GROUP BY date(created_at)
        ORDER BY d
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_series_leads_30_dias():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date(criado_em) AS d, COUNT(*)
        FROM leads
        WHERE criado_em IS NOT NULL
          AND date(criado_em) >= date('now', '-30 days')
        GROUP BY date(criado_em)
        ORDER BY d
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_export_usuarios_rows():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.id, u.email, COALESCE(u.bloqueado, 0),
               COALESCE(a.plano, 'FREE'), COALESCE(a.status, 'active')
        FROM usuarios u
        LEFT JOIN assinaturas a ON a.usuario_id = u.id
        ORDER BY u.id
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_export_leads_rows():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, nome, empresa, whatsapp, email, plano_interesse, criado_em, origem,
               COALESCE(status, 'novo'), COALESCE(observacoes, ''),
               COALESCE(atualizado_em, criado_em)
        FROM leads
        ORDER BY id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_export_analises_rows():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.id, a.empresa_id, e.nome AS empresa_nome, e.usuario_id,
               a.data_analise, a.tipo_caso, a.risco, a.pontuacao, a.versao_ia
        FROM analises a
        LEFT JOIN empresas e ON e.id = a.empresa_id
        ORDER BY a.id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def usuario_bloqueado(usuario_id) -> bool:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(bloqueado, 0) FROM usuarios WHERE id = ?",
        (usuario_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    return int(row[0] or 0) == 1


def usuario_acesso_suspenso_assinatura(usuario_id) -> bool:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT LOWER(COALESCE(status, 'active')) FROM assinaturas WHERE usuario_id = ?",
        (usuario_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    return str(row[0] or "").lower() == "suspended"


def usuario_pode_acessar_plataforma(usuario_id) -> bool:
    em = obter_email_usuario(usuario_id)
    if _email_admin_master(em) or usuario_eh_admin(usuario_id):
        return True
    if usuario_bloqueado(usuario_id):
        return False
    if usuario_acesso_suspenso_assinatura(usuario_id):
        return False
    return True


def admin_listar_usuarios_gestao():
    """id, email, bloqueado, plano, status_assinatura."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.id, u.email, COALESCE(u.bloqueado, 0),
               COALESCE(a.plano, 'FREE'), COALESCE(a.status, 'active')
        FROM usuarios u
        LEFT JOIN assinaturas a ON a.usuario_id = u.id
        ORDER BY u.id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_definir_bloqueio_usuario(usuario_id, bloqueado: int, actor_admin_id=None) -> bool:
    if int(bloqueado) == 1 and _email_admin_master(obter_email_usuario(usuario_id)):
        return False
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET bloqueado = ? WHERE id = ?",
        (1 if int(bloqueado) else 0, int(usuario_id)),
    )
    conn.commit()
    conn.close()
    registrar_admin_audit(
        admin_user_id=actor_admin_id,
        action="admin_set_user_block",
        target_type="usuario",
        target_id=str(usuario_id),
        details=f"bloqueado={1 if int(bloqueado) else 0}",
    )
    return True


def admin_definir_plano_e_status(usuario_id, plano: str, status_assinatura: str, actor_admin_id=None) -> bool:
    """Plano FREE|PRO|PREMIUM e status active|suspended (controle de acesso ao SaaS)."""
    if (
        str(status_assinatura or "").lower() == "suspended"
        and _email_admin_master(obter_email_usuario(usuario_id))
    ):
        return False
    plano = str(plano or "FREE").upper()
    if plano not in ("FREE", "PRO", "PREMIUM"):
        plano = "FREE"
    status_assinatura = str(status_assinatura or "active").lower()
    if status_assinatura not in ("active", "suspended"):
        status_assinatura = "active"
    definir_plano_usuario(int(usuario_id), plano, status=status_assinatura)
    registrar_admin_audit(
        admin_user_id=actor_admin_id,
        action="admin_set_plan_status",
        target_type="usuario",
        target_id=str(usuario_id),
        details=f"plano={plano};status={status_assinatura}",
    )
    return True


# =========================
# ADMIN · FINANCEIRO EXECUTIVO (somente leitura)
# =========================
_FIN_PRECO = {"FREE": 0.0, "PRO": 197.0, "PREMIUM": 397.0}


def _checkout_pago_sql(alias=""):
    """Predicado SQL para checkout considerado pago (alias opcional, ex.: 'c')."""
    col = f"{alias}.status" if alias else "status"
    return (
        f"(LOWER(TRIM(COALESCE({col}, ''))) IN ("
        f"'paid','approved','confirmed','recebido','succeeded','complete'"
        f"))"
    )


def admin_fin_kpis_executivo():
    """KPIs e indicadores financeiros para o painel admin."""
    mrr = admin_receita_estimada_mensal_brl()
    ym = datetime.now().strftime("%Y-%m")
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) FROM assinaturas
        WHERE COALESCE(status, 'active') = 'active'
          AND UPPER(COALESCE(plano, 'FREE')) IN ('PRO', 'PREMIUM')
        """
    )
    pagantes = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM assinaturas
        WHERE LOWER(COALESCE(status, '')) = 'suspended'
        """
    )
    suspensos_total = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM assinaturas
        WHERE COALESCE(status, 'active') = 'active'
          AND UPPER(COALESCE(plano, 'FREE')) = 'FREE'
        """
    )
    trials = int(cursor.fetchone()[0] or 0)

    ticket_medio = round(mrr / pagantes, 2) if pagantes > 0 else 0.0

    cursor.execute(
        f"""
        SELECT COUNT(DISTINCT usuario_id) FROM checkout_transacoes
        WHERE {_checkout_pago_sql()}
          AND strftime('%Y-%m', COALESCE(updated_at, created_at)) = ?
        """,
        (ym,),
    )
    upgrades_mes = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        f"""
        SELECT COUNT(*) FROM assinaturas a
        WHERE UPPER(COALESCE(a.plano, 'FREE')) = 'FREE'
          AND COALESCE(a.status, 'active') = 'active'
          AND strftime('%Y-%m', COALESCE(a.updated_at, a.created_at)) = ?
          AND EXISTS (
            SELECT 1 FROM checkout_transacoes c
            WHERE c.usuario_id = a.usuario_id
              AND {_checkout_pago_sql('c')}
          )
        """,
        (ym,),
    )
    downgrades_mes = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        """
        SELECT COUNT(*) FROM assinaturas
        WHERE LOWER(COALESCE(status, '')) = 'suspended'
          AND strftime('%Y-%m', COALESCE(updated_at, created_at)) = ?
        """,
        (ym,),
    )
    suspensos_mes = int(cursor.fetchone()[0] or 0)

    churn_est = (
        round(100.0 * suspensos_mes / max(1, pagantes), 1) if pagantes > 0 else 0.0
    )

    conn.close()

    return {
        "mrr_estimado": mrr,
        "pagantes_ativos": pagantes,
        "ticket_medio": ticket_medio,
        "suspensos_total": suspensos_total,
        "trials_ativos": trials,
        "upgrades_mes": upgrades_mes,
        "downgrades_mes": downgrades_mes,
        "churn_estimado_pct": churn_est,
        "suspensos_mes": suspensos_mes,
    }


def admin_fin_receita_por_plano():
    """Soma MRR estimado por plano pago (assinaturas ativas)."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT UPPER(COALESCE(plano, 'FREE')), COUNT(*)
        FROM assinaturas
        WHERE COALESCE(status, 'active') = 'active'
          AND UPPER(COALESCE(plano, 'FREE')) IN ('PRO', 'PREMIUM')
        GROUP BY UPPER(COALESCE(plano, 'FREE'))
        """
    )
    rows = cursor.fetchall()
    conn.close()
    out = []
    for plano, cnt in rows:
        p = str(plano or "FREE").upper()
        preco = float(_FIN_PRECO.get(p, 0.0))
        out.append((p, round(preco * int(cnt or 0), 2)))
    return out


def admin_fin_base_por_plano():
    """Contagem de assinaturas ativas por plano."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT UPPER(COALESCE(plano, 'FREE')), COUNT(*)
        FROM assinaturas
        WHERE COALESCE(status, 'active') = 'active'
        GROUP BY UPPER(COALESCE(plano, 'FREE'))
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [(str(a or "FREE").upper(), int(b or 0)) for a, b in rows]


def admin_fin_checkout_volume_mensal_6m():
    """
    Soma valores de checkout pagos por mês (últimos 6 meses).
    Proxy de evolução de receita transacional (não é MRR contábil exato).
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT strftime('%Y-%m', COALESCE(updated_at, created_at)) AS ym,
               SUM(COALESCE(valor, 0))
        FROM checkout_transacoes
        WHERE {_checkout_pago_sql()}
          AND date(COALESCE(updated_at, created_at)) >= date('now', '-200 days')
        GROUP BY ym
        ORDER BY ym
        """
    )
    raw = cursor.fetchall()
    conn.close()
    return [(str(r[0]), float(r[1] or 0)) for r in raw]


def admin_fin_ultimos_checkouts_pagos(limit=15):
    """Últimos upgrades / pagamentos confirmados."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT c.usuario_id, u.email, c.plano_destino, COALESCE(c.valor, 0),
               COALESCE(c.updated_at, c.created_at), c.status
        FROM checkout_transacoes c
        INNER JOIN usuarios u ON u.id = c.usuario_id
        WHERE {_checkout_pago_sql('c')}
        ORDER BY datetime(COALESCE(c.updated_at, c.created_at)) DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_fin_ultimos_suspensos(limit=15):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.usuario_id, u.email, COALESCE(a.plano, ''),
               COALESCE(a.updated_at, a.created_at)
        FROM assinaturas a
        INNER JOIN usuarios u ON u.id = a.usuario_id
        WHERE LOWER(COALESCE(a.status, '')) = 'suspended'
        ORDER BY datetime(COALESCE(a.updated_at, a.created_at)) DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_alertas_automaticos():
    """
    Alertas comparativos (somente leitura). Retorna lista de dicts com
    key, nivel (warning|danger|success|info), titulo, texto.
    """
    alerts = []
    conn = conectar()
    c = conn.cursor()

    c.execute(
        """
        SELECT COUNT(*) FROM leads
        WHERE date(criado_em) >= date('now', '-7 days')
        """
    )
    leads_curr = int(c.fetchone()[0] or 0)
    c.execute(
        """
        SELECT COUNT(*) FROM leads
        WHERE date(criado_em) >= date('now', '-14 days')
          AND date(criado_em) < date('now', '-7 days')
        """
    )
    leads_prev = int(c.fetchone()[0] or 0)
    if leads_prev >= 3:
        ratio = leads_curr / float(leads_prev) if leads_prev else 0.0
        if ratio <= 0.80:
            pct = round(100.0 * (ratio - 1.0), 1)
            alerts.append(
                {
                    "key": "leads_queda",
                    "nivel": "warning",
                    "titulo": "Queda de leads (7 dias)",
                    "texto": (
                        f"Últimos 7 dias: {leads_curr} leads vs {leads_prev} na semana anterior "
                        f"({pct:+.0f}% vs janela anterior). Revisar captação e campanhas."
                    ),
                }
            )
    elif leads_prev > 0 and leads_curr == 0:
        alerts.append(
            {
                "key": "leads_queda",
                "nivel": "danger",
                "titulo": "Leads interrompidos",
                "texto": (
                    f"Nenhum lead nos últimos 7 dias; na semana anterior havia {leads_prev}. "
                    "Verificar landing e canais."
                ),
            }
        )

    c.execute(
        """
        SELECT COUNT(*) FROM assinaturas
        WHERE LOWER(COALESCE(status, '')) = 'suspended'
          AND date(COALESCE(updated_at, created_at)) >= date('now', '-7 days')
        """
    )
    susp_curr = int(c.fetchone()[0] or 0)
    c.execute(
        """
        SELECT COUNT(*) FROM assinaturas
        WHERE LOWER(COALESCE(status, '')) = 'suspended'
          AND date(COALESCE(updated_at, created_at)) >= date('now', '-14 days')
          AND date(COALESCE(updated_at, created_at)) < date('now', '-7 days')
        """
    )
    susp_prev = int(c.fetchone()[0] or 0)
    if susp_prev >= 1 and susp_curr >= max(2, int(susp_prev * 1.4)):
        alerts.append(
            {
                "key": "churn_subida",
                "nivel": "danger",
                "titulo": "Aumento de suspensões (churn)",
                "texto": (
                    f"Suspensões de assinatura: {susp_curr} (7d) vs {susp_prev} (7d anteriores). "
                    "Acompanhar retenção e suporte."
                ),
            }
        )
    elif susp_prev == 0 and susp_curr >= 3:
        alerts.append(
            {
                "key": "churn_subida",
                "nivel": "warning",
                "titulo": "Picos de suspensões",
                "texto": (
                    f"{susp_curr} suspensões nos últimos 7 dias, sem base na semana anterior. "
                    "Verificar cobrança e uso."
                ),
            }
        )

    c.execute(
        f"""
        SELECT COALESCE(SUM(valor), 0) FROM checkout_transacoes
        WHERE {_checkout_pago_sql()}
          AND date(COALESCE(updated_at, created_at)) >= date('now', '-30 days')
        """
    )
    rev_curr = float(c.fetchone()[0] or 0)
    c.execute(
        f"""
        SELECT COALESCE(SUM(valor), 0) FROM checkout_transacoes
        WHERE {_checkout_pago_sql()}
          AND date(COALESCE(updated_at, created_at)) >= date('now', '-60 days')
          AND date(COALESCE(updated_at, created_at)) < date('now', '-30 days')
        """
    )
    rev_prev = float(c.fetchone()[0] or 0)
    if rev_prev > 0 and rev_curr >= rev_prev * 1.08:
        pct = round(100.0 * (rev_curr / rev_prev - 1.0), 1)
        alerts.append(
            {
                "key": "receita_sobe",
                "nivel": "success",
                "titulo": "Receita (checkout) em alta",
                "texto": (
                    f"Volume de checkout pago: R$ {rev_curr:,.2f} (30d) vs "
                    f"R$ {rev_prev:,.2f} (30d anteriores) · +{pct:.1f}%."
                ),
            }
        )
    elif rev_prev == 0 and rev_curr > 500:
        alerts.append(
            {
                "key": "receita_sobe",
                "nivel": "success",
                "titulo": "Checkout aquecido",
                "texto": (
                    f"R$ {rev_curr:,.2f} em checkout pago nos últimos 30 dias "
                    "(sem janela anterior comparável)."
                ),
            }
        )

    c.execute(
        """
        SELECT COUNT(DISTINCT a.usuario_id)
        FROM assinaturas a
        WHERE COALESCE(a.status, 'active') = 'active'
          AND UPPER(COALESCE(a.plano, 'FREE')) IN ('PRO', 'PREMIUM')
          AND NOT EXISTS (
            SELECT 1 FROM analises an
            INNER JOIN empresas e ON e.id = an.empresa_id AND e.usuario_id = a.usuario_id
            WHERE date(an.data_analise) >= date('now', '-14 days')
          )
        """
    )
    inativos = int(c.fetchone()[0] or 0)
    if inativos >= 1:
        alerts.append(
            {
                "key": "usuarios_inativos",
                "nivel": "info",
                "titulo": "Usuários pagantes sem uso recente",
                "texto": (
                    f"{inativos} conta(s) PRO/Business ativa(s) sem análise nos últimos 14 dias. "
                    "Oportunidade de sucesso do cliente e upsell."
                ),
            }
        )

    conn.close()
    return alerts