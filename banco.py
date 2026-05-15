import binascii
import csv
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import create_engine

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

# Render define RENDER=true nos Web Services (documentação oficial).
_IS_RENDER = str(os.getenv("RENDER", "")).strip().lower() in {"1", "true", "yes"}

# PostgreSQL: somente quando DATABASE_URL está definida (Render ou desenvolvimento com Postgres).
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()


def _normalize_database_url(database_url: str) -> str:
    """
    Render costuma fornecer DATABASE_URL começando com postgres://.
    SQLAlchemy exige driver explícito quando queremos psycopg2.
    """
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg2://" + database_url[len("postgres://"):]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + database_url[len("postgresql://"):]
    return database_url


def _postgres_engine_url() -> str | None:
    """Retorna URL SQLAlchemy para psycopg2, ou None se não houver Postgres configurado."""
    if not DATABASE_URL:
        return None
    normalized = _normalize_database_url(DATABASE_URL)
    return normalized or None


def _build_engine():
    """
    Render com Postgres: exige DATABASE_URL (evita cair em SQLite por engano).
    Local: SQLite em arquivo quando DATABASE_URL está vazia; caso contrário Postgres.
    """
    pg_url = _postgres_engine_url()

    if _IS_RENDER:
        if not pg_url:
            raise RuntimeError(
                "Ambiente Render detectado (RENDER=true), mas DATABASE_URL não está definida. "
                "Configure DATABASE_URL no Web Service apontando para o Postgres."
            )
        return create_engine(pg_url, pool_pre_ping=True, future=True)

    if pg_url:
        return create_engine(pg_url, pool_pre_ping=True, future=True)

    return create_engine(
        f"sqlite:///{DB_NAME}",
        future=True,
        connect_args={"check_same_thread": False},
    )


ENGINE = _build_engine()
# Dialetal real do engine (postgresql vs sqlite); `conectar()` usa psycopg2 via raw_connection em Postgres.
IS_POSTGRES = ENGINE.dialect.name == "postgresql"


def _replace_qmark_placeholders(sql: str) -> str:
    """Converte placeholders `?` para `%s` (psycopg2), respeitando strings SQL."""
    out = []
    in_single = False
    in_double = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
        elif ch == "?" and not in_single and not in_double:
            out.append("%s")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _sqlite_autoincrement_to_postgres(sql: str) -> str:
    return re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "BIGSERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )


def _sqlite_insert_or_replace_to_postgres(sql: str) -> str:
    """
    Tradução compatível para padrão legado:
    INSERT OR REPLACE INTO tabela (c1, c2, ...) VALUES (...)
    -> INSERT ... ON CONFLICT (c1) DO UPDATE SET ...
    """
    pattern = re.compile(
        r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*"
        r"\((.*?)\)\s*VALUES\s*\((.*?)\)\s*;?\s*$",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.match(sql)
    if not match:
        return sql
    table_name = match.group(1).strip()
    raw_columns = match.group(2).strip()
    raw_values = match.group(3).strip()
    columns = [c.strip() for c in raw_columns.split(",") if c.strip()]
    if not columns:
        return sql
    conflict_col = columns[0]
    update_columns = [c for c in columns if c != conflict_col]
    if not update_columns:
        return (
            f"INSERT INTO {table_name} ({raw_columns}) VALUES ({raw_values}) "
            f"ON CONFLICT ({conflict_col}) DO NOTHING"
        )
    set_clause = ", ".join(f"{col} = EXCLUDED.{col}" for col in update_columns)
    return (
        f"INSERT INTO {table_name} ({raw_columns}) VALUES ({raw_values}) "
        f"ON CONFLICT ({conflict_col}) DO UPDATE SET {set_clause}"
    )


def _adapt_sql_for_postgres(sql: str) -> str:
    sql = _sqlite_insert_or_replace_to_postgres(sql)
    sql = _sqlite_autoincrement_to_postgres(sql)
    sql = _replace_qmark_placeholders(sql)
    return sql


class _CompatCursor:
    def __init__(self, cursor, owner_connection):
        self._cursor = cursor
        self._owner_connection = owner_connection
        self.lastrowid = None

    def execute(self, sql, params=None):
        try:
            adapted_sql = _adapt_sql_for_postgres(sql) if IS_POSTGRES else sql
            if params is None:
                result = self._cursor.execute(adapted_sql)
            else:
                result = self._cursor.execute(adapted_sql, params)
            if IS_POSTGRES and adapted_sql.strip().upper().startswith("INSERT INTO"):
                self._refresh_lastrowid()
            return result
        except Exception as exc:
            # Mantém compatibilidade com os vários `except sqlite3.OperationalError` no arquivo.
            raise sqlite3.OperationalError(str(exc)) from exc

    def _refresh_lastrowid(self):
        try:
            probe = self._owner_connection._raw_connection.cursor()
            probe.execute("SELECT LASTVAL()")
            row = probe.fetchone()
            probe.close()
            self.lastrowid = row[0] if row else None
        except Exception:
            self.lastrowid = None

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class _CompatConnection:
    def __init__(self, raw_connection):
        self._raw_connection = raw_connection

    def cursor(self):
        return _CompatCursor(self._raw_connection.cursor(), self)

    def commit(self):
        return self._raw_connection.commit()

    def rollback(self):
        return self._raw_connection.rollback()

    def close(self):
        return self._raw_connection.close()


def _admin_master_email() -> str | None:
    raw = os.environ.get("ADMIN_MASTER_EMAIL")
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip().lower()


def _admin_master_password_for_sync() -> str | None:
    """
    Senha em texto vinda de ADMIN_MASTER_PASSWORD para bootstrap/sync no deploy.
    Ausente, vazia ou com menos de 8 caracteres: não sincroniza (alinha a atualizar_senha_usuario).
    """
    raw = os.environ.get("ADMIN_MASTER_PASSWORD")
    if raw is None:
        return None
    s = str(raw).strip()
    if len(s) < 8:
        return None
    return s


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
    """
    Abre conexão de acordo com o ambiente:
    - DATABASE_URL definida (ou obrigatoriamente no Render): SQLAlchemy + psycopg2 → Postgres.
    - Sem DATABASE_URL fora do Render: SQLite (sqlite3 via SQLAlchemy).
    """
    raw_connection = ENGINE.raw_connection()
    if IS_POSTGRES:
        return _CompatConnection(raw_connection)
    return raw_connection


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


def _normalizar_senha_hash_db(raw) -> bytes:
    """
    Converte senha_hash do driver para bytes usados pelo bcrypt.
    Recupera representações hex do psycopg2 (prefixo \\x...) em hashes antigos/corrompidos.
    """
    if raw is None:
        return b""
    if isinstance(raw, (bytes, bytearray, memoryview)):
        val = bytes(raw)
    else:
        val = str(raw or "").encode("utf-8")

    if val.startswith(b"\\x"):
        try:
            val = binascii.unhexlify(val[2:])
        except Exception:
            pass

    return val


def _senha_hash_bcrypt_valida(s: str) -> bool:
    """
    True se parecer um bcrypt válido ($2a$ / $2b$ / $2y$, comprimento típico).
    Hashes corrompidos (hex SHA-256, texto curto, etc.) falham aqui.
    """
    if not s or not isinstance(s, str):
        return False
    t = s.strip()
    if len(t) < 59:
        return False
    return t.startswith("$2a$") or t.startswith("$2b$") or t.startswith("$2y$")


def _bootstrap_admin_master():
    """
    Bootstrap via ADMIN_MASTER_EMAIL (+ ADMIN_MASTER_PASSWORD opcional mas recomendado):
    - Garante somente este e-mail com is_admin=1 (demais is_admin=0).
    - Se ADMIN_MASTER_PASSWORD estiver definida (≥8 caracteres):
      - usuário inexistente: cria conta com essa senha (fluxo criar_usuario);
      - usuário existente: atualiza senha_hash para espelhar o ambiente a cada deploy.
    - Se senha_hash existente estiver corrompida e ADMIN_MASTER_PASSWORD estiver definida,
      grava novo hash bcrypt como texto UTF-8 (adequado ao Postgres).
    """
    raw_email = (os.environ.get("ADMIN_MASTER_EMAIL") or "").strip()
    if not raw_email:
        return
    master_lower = raw_email.lower()
    pwd_sync = _admin_master_password_for_sync()

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM usuarios
        WHERE LOWER(TRIM(COALESCE(email, ''))) = ?
        """,
        (master_lower,),
    )
    row = cursor.fetchone()

    usuario_id = int(row[0]) if row else None

    hash_ok = True
    if usuario_id is not None:
        cursor.execute(
            "SELECT senha_hash FROM usuarios WHERE id = ?",
            (usuario_id,),
        )
        hrow = cursor.fetchone()
        raw_hash = hrow[0] if hrow else None
        senha_hash_bytes = _normalizar_senha_hash_db(raw_hash)
        try:
            senha_hash_str = senha_hash_bytes.decode("utf-8")
        except Exception:
            senha_hash_str = ""
        hash_ok = _senha_hash_bcrypt_valida(senha_hash_str)

    if usuario_id is not None and not hash_ok and not pwd_sync:
        print(
            "[bootstrap_admin_master] AVISO: senha_hash do admin master parece invalida; "
            "defina ADMIN_MASTER_PASSWORD (>=8 caracteres) para reparar no proximo deploy.",
            flush=True,
        )

    if pwd_sync:
        senha_hash_txt = bcrypt.hashpw(
            pwd_sync.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        if row:
            if not hash_ok:
                print(
                    "[bootstrap_admin_master] senha_hash do admin master reparada "
                    "(valor anterior invalido ou ausente).",
                    flush=True,
                )
            cursor.execute(
                "UPDATE usuarios SET senha_hash = ? WHERE id = ?",
                (senha_hash_txt, usuario_id),
            )
        else:
            conn.commit()
            conn.close()
            criar_usuario(raw_email, pwd_sync)
            conn = conectar()
            cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE usuarios
        SET is_admin = CASE
            WHEN LOWER(TRIM(COALESCE(email, ''))) = ? THEN 1
            ELSE 0
        END
        """,
        (master_lower,),
    )
    cursor.execute(
        """
        UPDATE usuarios
        SET is_admin = 1
        WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))
        """,
        (raw_email,),
    )
    conn.commit()
    conn.close()


def _garantir_coluna_usuarios_nome():
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN nome TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _garantir_coluna_usuarios_reset_token():
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN reset_token TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _garantir_coluna_usuarios_reset_token_expires():
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN reset_token_expires TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _garantir_coluna_usuarios_data_criacao():
    """Data de cadastro do usuário (TEXT ISO); Postgres legado pode não ter criado_em."""
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN data_criacao TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _garantir_coluna_analises_criado_por():
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "ALTER TABLE analises ADD COLUMN criado_por_usuario_id INTEGER"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def _migrar_equipe_permissoes_padrao():
    """Backfill: cada empresa existente ganha o proprietário como admin na tabela empresa_membros."""
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        SELECT id, usuario_id FROM empresas
        WHERE usuario_id IS NOT NULL
        """
    )
    for empresa_id, proprietario_id in cursor.fetchall():
        cursor.execute(
            """
            INSERT INTO empresa_membros (usuario_id, empresa_id, perfil, criado_em)
            VALUES (?, ?, 'admin', ?)
            ON CONFLICT(usuario_id, empresa_id) DO NOTHING
            """,
            (int(proprietario_id), int(empresa_id), agora),
        )
    cursor.execute(
        """
        UPDATE analises SET criado_por_usuario_id = (
            SELECT usuario_id FROM empresas WHERE empresas.id = analises.empresa_id
        )
        WHERE criado_por_usuario_id IS NULL
        """
    )
    conn.commit()
    conn.close()


PERFIS_EQUIPE_VALIDOS = frozenset({"admin", "gestor", "colaborador"})
STATUS_CONVITE_VALIDOS = frozenset({"pendente", "aceito", "expirado", "cancelado"})

# Registro técnico em `analises` para amarrar fatos validados antes do relatório completo (excluir de insights/resumos).
TIPO_ANALISE_STUB_VALIDACAO_FATOS = "validacao_fatos_documento"


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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico_status_usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        status_anterior TEXT,
        status_novo TEXT NOT NULL,
        alterado_em TEXT NOT NULL,
        alterado_por TEXT NOT NULL,
        motivo TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico_planos_assinatura (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assinatura_id INTEGER,
        usuario_id INTEGER NOT NULL,
        plano_anterior TEXT,
        plano_novo TEXT NOT NULL,
        status_anterior TEXT,
        status_novo TEXT NOT NULL,
        alterado_em TEXT NOT NULL,
        alterado_por TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eventos_produto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        empresa_id INTEGER,
        nome_evento TEXT NOT NULL,
        timestamp_evento TEXT NOT NULL,
        metadados_json TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS empresa_membros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        empresa_id INTEGER NOT NULL,
        perfil TEXT NOT NULL,
        criado_em TEXT,
        UNIQUE(usuario_id, empresa_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analises_fatos_validados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analise_id INTEGER NOT NULL,
        nome_fato TEXT NOT NULL,
        valor_fato TEXT,
        fonte TEXT NOT NULL,
        validado_em TEXT NOT NULL,
        validado_por_usuario_id INTEGER NOT NULL,
        UNIQUE(analise_id, nome_fato)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS empresa_api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL,
        api_key_hash TEXT NOT NULL UNIQUE,
        criada_em TEXT NOT NULL,
        revogada_em TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS empresa_funcionarios_integracao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL,
        employee_id_externo TEXT NOT NULL,
        nome_completo TEXT NOT NULL,
        data_admissao TEXT,
        cargo TEXT,
        salario_bruto REAL,
        tipo_contrato TEXT,
        ultima_atualizacao TEXT NOT NULL,
        UNIQUE(empresa_id, employee_id_externo)
    )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_empresa_api_keys_empresa ON empresa_api_keys(empresa_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_empresa_func_int_empresa ON empresa_funcionarios_integracao(empresa_id)"
    )

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS empresa_auditorias_risco (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL,
        executada_em TEXT NOT NULL,
        executada_por_usuario_id INTEGER NOT NULL,
        resultado_json TEXT NOT NULL
    )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_auditorias_risco_empresa ON empresa_auditorias_risco(empresa_id)"
    )
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS empresa_convites_primeiro_acesso (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER NOT NULL,
        usuario_id INTEGER NOT NULL,
        email TEXT NOT NULL,
        nome_convidado TEXT,
        perfil TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'pendente',
        convidado_por_usuario_id INTEGER NOT NULL,
        criado_em TEXT NOT NULL,
        expira_em TEXT NOT NULL,
        aceito_em TEXT
    )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_convites_empresa_status ON empresa_convites_primeiro_acesso(empresa_id, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_convites_email_status ON empresa_convites_primeiro_acesso(email, status)"
    )

    conn.commit()
    conn.close()
    _garantir_coluna_usuarios_bloqueado()
    _garantir_coluna_usuarios_is_admin()
    _garantir_coluna_usuarios_nome()
    _garantir_coluna_usuarios_reset_token()
    _garantir_coluna_usuarios_reset_token_expires()
    _garantir_coluna_usuarios_data_criacao()
    _garantir_coluna_analises_criado_por()
    _garantir_colunas_leads_crm()
    _bootstrap_admin_master()
    _migrar_equipe_permissoes_padrao()


def criar_tabelas_e_migrar():
    """
    Ponto de entrada de bootstrap para ambientes de deploy.
    Mantém compatibilidade com scripts de inicialização (Render/start.sh).
    """
    criar_tabelas()


def registrar_mudanca_status_usuario(
    usuario_id,
    status_anterior: str | None,
    status_novo: str,
    alterado_por: str = "sistema",
    motivo: str | None = None,
):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO historico_status_usuario (
            usuario_id, status_anterior, status_novo, alterado_em, alterado_por, motivo
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(usuario_id),
            str(status_anterior or "").strip() or None,
            str(status_novo or "").strip() or "ativo",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(alterado_por or "sistema").strip() or "sistema",
            str(motivo).strip() if motivo is not None else None,
        ),
    )
    conn.commit()
    conn.close()


def registrar_mudanca_plano_assinatura(
    assinatura_id,
    usuario_id,
    plano_anterior: str | None,
    plano_novo: str,
    status_anterior: str | None,
    status_novo: str,
    alterado_por: str = "sistema",
):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO historico_planos_assinatura (
            assinatura_id,
            usuario_id,
            plano_anterior,
            plano_novo,
            status_anterior,
            status_novo,
            alterado_em,
            alterado_por
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(assinatura_id) if assinatura_id is not None else None,
            int(usuario_id),
            str(plano_anterior or "").strip() or None,
            str(plano_novo or "").strip() or "FREE",
            str(status_anterior or "").strip() or None,
            str(status_novo or "").strip() or "active",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(alterado_por or "sistema").strip() or "sistema",
        ),
    )
    conn.commit()
    conn.close()


def registrar_evento_produto(
    nome_evento: str,
    usuario_id=None,
    empresa_id=None,
    metadados: dict | None = None,
):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO eventos_produto (
            usuario_id, empresa_id, nome_evento, timestamp_evento, metadados_json
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(usuario_id) if usuario_id is not None else None,
            int(empresa_id) if empresa_id is not None else None,
            str(nome_evento or "").strip() or "evento_produto",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            json.dumps(metadados or {}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def _colunas_existentes_leads() -> set[str]:
    """Lista nomes de colunas da tabela `leads` (SQLite ou PostgreSQL)."""
    conn = conectar()
    cursor = conn.cursor()
    try:
        if IS_POSTGRES:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'leads'
                """
            )
            return {str(row[0] or "").lower() for row in cursor.fetchall()}
        cursor.execute("PRAGMA table_info(leads)")
        return {str(row[1] or "").lower() for row in cursor.fetchall()}
    finally:
        conn.close()


def _adicionar_coluna_leads_se_faltar(nome_coluna: str, definicao_sql: str) -> None:
    """
    Executa um ALTER TABLE isolado com commit próprio.
    Evita InFailedSqlTransaction no Postgres quando uma migração falha ou coluna já existe.
    """
    nome_coluna = str(nome_coluna or "").strip().lower()
    if not nome_coluna:
        return
    conn = conectar()
    cursor = conn.cursor()
    try:
        stmt = f'ALTER TABLE leads ADD COLUMN "{nome_coluna}" {definicao_sql}'
        cursor.execute(stmt)
        conn.commit()
    except sqlite3.OperationalError as exc:
        conn.rollback()
        msg = str(exc).lower()
        if "duplicate column" in msg or "already exists" in msg:
            return
        raise
    finally:
        conn.close()


def _garantir_colunas_leads_crm():
    """
    Migração leve das colunas de CRM na tabela `leads`.
    Compatível com PostgreSQL: consulta information_schema e cada ALTER em transação isolada.
    """
    existentes = _colunas_existentes_leads()

    # Tipagem compatível com Postgres e SQLite (TEXT).
    desejadas = (
        ("status", "TEXT DEFAULT 'novo'"),
        ("observacoes", "TEXT DEFAULT ''"),
        ("atualizado_em", "TEXT"),
    )

    for nome, ddl in desejadas:
        if nome.lower() in existentes:
            continue
        _adicionar_coluna_leads_se_faltar(nome, ddl)
        existentes.add(nome.lower())

    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE leads SET atualizado_em = criado_em
            WHERE atualizado_em IS NULL OR TRIM(COALESCE(atualizado_em::text, '')) = ''
            """
            if IS_POSTGRES
            else """
            UPDATE leads SET atualizado_em = criado_em
            WHERE atualizado_em IS NULL OR TRIM(atualizado_em) = ''
            """
        )
        cursor.execute(
            """
            UPDATE leads SET status = 'novo'
            WHERE status IS NULL OR TRIM(COALESCE(status::text, '')) = ''
            """
            if IS_POSTGRES
            else """
            UPDATE leads SET status = 'novo'
            WHERE status IS NULL OR TRIM(status) = ''
            """
        )
        conn.commit()
    finally:
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
EMAIL_JA_CADASTRADO_MSG = "E-mail já cadastrado"


def criar_usuario(email, senha, nome=None):
    email_norm = str(email or "").strip()
    if not email_norm:
        raise ValueError("E-mail inválido")
    if obter_usuario_id_por_email(email_norm):
        raise ValueError(EMAIL_JA_CADASTRADO_MSG)

    conn = conectar()
    cursor = conn.cursor()

    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    nome_val = (nome or "").strip() or None
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO usuarios (email, senha_hash, nome, data_criacao)
    VALUES (?, ?, ?, ?)
    """, (email_norm, senha_hash, nome_val, agora))

    usuario_id = cursor.lastrowid

    if IS_POSTGRES:
        sql_assinaturas = """
        INSERT INTO assinaturas (
            usuario_id,
            plano,
            status,
            billing_cycle,
            created_at,
            updated_at
        )
        VALUES (?, 'FREE', 'active', 'monthly', ?, ?)
        ON CONFLICT (usuario_id) DO NOTHING
        """
    else:
        sql_assinaturas = """
        INSERT OR IGNORE INTO assinaturas (
            usuario_id,
            plano,
            status,
            billing_cycle,
            created_at,
            updated_at
        )
        VALUES (?, 'FREE', 'active', 'monthly', ?, ?)
        """
    cursor.execute(sql_assinaturas, (usuario_id, agora, agora))

    if IS_POSTGRES:
        sql_onboarding = """
        INSERT INTO onboarding_usuario (
            usuario_id,
            etapa_atual,
            concluido,
            criado_em,
            atualizado_em
        )
        VALUES (?, 1, 0, ?, ?)
        ON CONFLICT (usuario_id) DO NOTHING
        """
    else:
        sql_onboarding = """
        INSERT OR IGNORE INTO onboarding_usuario (
            usuario_id,
            etapa_atual,
            concluido,
            criado_em,
            atualizado_em
        )
        VALUES (?, 1, 0, ?, ?)
        """
    cursor.execute(sql_onboarding, (usuario_id, agora, agora))

    conn.commit()
    conn.close()
    return usuario_id


def obter_usuario_id_por_email(email: str):
    if not email or not str(email).strip():
        return None
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM usuarios WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))",
        (email.strip(),),
    )
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else None


def atualizar_nome_usuario(usuario_id, nome: str):
    nome = (nome or "").strip()
    if not nome:
        return
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET nome = ? WHERE id = ?",
        (nome, int(usuario_id)),
    )
    conn.commit()
    conn.close()


def atualizar_senha_usuario(usuario_id, nova_senha: str):
    senha = str(nova_senha or "")
    if len(senha) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET senha_hash = ? WHERE id = ?",
        (senha_hash, int(usuario_id)),
    )
    conn.commit()
    conn.close()


_RESET_TOKEN_VIDA_HORAS = 1


def _hash_reset_token(token_plain: str) -> str:
    return hashlib.sha256(str(token_plain).strip().encode("utf-8")).hexdigest()


def gerar_token_reset_senha(email: str | None) -> str | None:
    """
    Gera token seguro, persiste hash + expiração em usuarios e retorna o token em texto claro
    (uso único: enviar por e-mail). Retorna None se o e-mail não existir.
    """
    em = (email or "").strip().lower()
    if not em:
        return None
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM usuarios
        WHERE LOWER(TRIM(COALESCE(email, ''))) = ?
        """,
        (em,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None

    usuario_id = int(row[0])
    token_plain = secrets.token_urlsafe(48)
    token_hash = _hash_reset_token(token_plain)
    expira = datetime.now() + timedelta(hours=_RESET_TOKEN_VIDA_HORAS)
    expira_txt = expira.strftime("%Y-%m-%d %H:%M:%S")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE usuarios
        SET reset_token = ?, reset_token_expires = ?
        WHERE id = ?
        """,
        (token_hash, expira_txt, usuario_id),
    )
    conn.commit()
    conn.close()
    return token_plain


def validar_token_e_resetar_senha(token: str | None, nova_senha: str) -> tuple[bool, str]:
    """
    Valida token de reset e define nova senha. Limpa reset_token / reset_token_expires em caso de sucesso.
    Retorna (ok, mensagem).
    """
    senha = str(nova_senha or "")
    if len(senha) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres."

    token_limpo = str(token or "").strip()
    if not token_limpo:
        return False, "Token inválido."

    token_hash = _hash_reset_token(token_limpo)

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, COALESCE(reset_token_expires, '')
        FROM usuarios
        WHERE reset_token IS NOT NULL AND reset_token = ?
        """,
        (token_hash,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "Token inválido ou expirado."

    usuario_id = int(row[0])
    expira_raw = str(row[1] or "").strip()
    conn.close()

    if not expira_raw:
        return False, "Token inválido ou expirado."

    try:
        expira_dt = datetime.strptime(expira_raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False, "Token inválido ou expirado."

    if datetime.now() > expira_dt:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE usuarios SET reset_token = NULL, reset_token_expires = NULL WHERE id = ?
            """,
            (usuario_id,),
        )
        conn.commit()
        conn.close()
        return False, "Token expirado. Solicite uma nova redefinição de senha."

    try:
        atualizar_senha_usuario(usuario_id, senha)
    except ValueError as exc:
        return False, str(exc)

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE usuarios
        SET reset_token = NULL, reset_token_expires = NULL
        WHERE id = ?
        """,
        (usuario_id,),
    )
    conn.commit()
    conn.close()
    return True, "Senha atualizada com sucesso."


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

    # Recupera hashes antigos gravados como \\x... (hex do psycopg2) via _normalizar_senha_hash_db.
    senha_hash_bytes = _normalizar_senha_hash_db(senha_hash)
    if not senha_hash_bytes:
        return None

    if bcrypt.checkpw(str(senha or "").encode("utf-8"), senha_hash_bytes):
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


def is_usuario_admin(usuario_id) -> bool:
    """True se o usuário tem is_admin=1 na tabela usuarios."""
    if usuario_id is None:
        return False
    return usuario_eh_admin(usuario_id)


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

    empresa_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return int(empresa_id)


def listar_empresas(usuario_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DISTINCT e.id, e.nome
        FROM empresas e
        INNER JOIN empresa_membros m ON m.empresa_id = e.id AND m.usuario_id = ?
        ORDER BY e.nome ASC
        """,
        (usuario_id,),
    )

    dados = cursor.fetchall()
    conn.close()
    return dados


def listar_todas_as_empresas() -> list[dict]:
    """
    Catálogo global de empresas para Super Admin.
    Retorna id, nome, cnpj, data de criação e e-mail do proprietário original.
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            e.id,
            COALESCE(e.usuario_id, 0) AS id_proprietario,
            COALESCE(e.nome, '') AS nome_empresa,
            COALESCE(e.cnpj, '') AS cnpj,
            COALESCE(e.data_cadastro, '') AS data_criacao_empresa,
            COALESCE(u.email, '') AS email_proprietario,
            UPPER(COALESCE(a.plano, 'FREE')) AS plano_atual
        FROM empresas e
        LEFT JOIN usuarios u ON u.id = e.usuario_id
        LEFT JOIN assinaturas a ON a.usuario_id = e.usuario_id
        ORDER BY e.id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id_empresa": int(r[0]),
            "id_proprietario": int(r[1] or 0),
            "nome_empresa": str(r[2] or ""),
            "cnpj": str(r[3] or ""),
            "data_criacao_empresa": str(r[4] or ""),
            "email_proprietario": str(r[5] or ""),
            "plano_atual": str(r[6] or "FREE").upper(),
        }
        for r in rows
    ]


def listar_historico_status_usuario(limit=100) -> list[dict]:
    conn = conectar()
    cursor = conn.cursor()
    lim = max(1, int(limit or 100))
    cursor.execute(
        f"""
        SELECT
            h.id,
            h.usuario_id,
            COALESCE(u.email, '') AS email_usuario,
            COALESCE(h.status_anterior, '') AS status_anterior,
            COALESCE(h.status_novo, '') AS status_novo,
            COALESCE(h.alterado_em, '') AS alterado_em,
            COALESCE(h.alterado_por, '') AS alterado_por,
            COALESCE(h.motivo, '') AS motivo
        FROM historico_status_usuario h
        LEFT JOIN usuarios u ON u.id = h.usuario_id
        ORDER BY {_sql_order_ts_desc("h.alterado_em")}, h.id DESC
        LIMIT ?
        """,
        (lim,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": int(r[0]),
            "usuario_id": int(r[1] or 0),
            "email_usuario": str(r[2] or ""),
            "status_anterior": str(r[3] or ""),
            "status_novo": str(r[4] or ""),
            "alterado_em": str(r[5] or ""),
            "alterado_por": str(r[6] or ""),
            "motivo": str(r[7] or ""),
        }
        for r in rows
    ]


def listar_historico_planos_assinatura(limit=100) -> list[dict]:
    conn = conectar()
    cursor = conn.cursor()
    lim = max(1, int(limit or 100))
    cursor.execute(
        f"""
        SELECT
            h.id,
            h.assinatura_id,
            h.usuario_id,
            COALESCE(u.email, '') AS email_usuario,
            COALESCE(h.plano_anterior, '') AS plano_anterior,
            COALESCE(h.plano_novo, '') AS plano_novo,
            COALESCE(h.status_anterior, '') AS status_anterior,
            COALESCE(h.status_novo, '') AS status_novo,
            COALESCE(h.alterado_em, '') AS alterado_em,
            COALESCE(h.alterado_por, '') AS alterado_por
        FROM historico_planos_assinatura h
        LEFT JOIN usuarios u ON u.id = h.usuario_id
        ORDER BY {_sql_order_ts_desc("h.alterado_em")}, h.id DESC
        LIMIT ?
        """,
        (lim,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": int(r[0]),
            "assinatura_id": int(r[1] or 0) if r[1] is not None else None,
            "usuario_id": int(r[2] or 0),
            "email_usuario": str(r[3] or ""),
            "plano_anterior": str(r[4] or ""),
            "plano_novo": str(r[5] or ""),
            "status_anterior": str(r[6] or ""),
            "status_novo": str(r[7] or ""),
            "alterado_em": str(r[8] or ""),
            "alterado_por": str(r[9] or ""),
        }
        for r in rows
    ]


def listar_eventos_produto(limit=100) -> list[dict]:
    conn = conectar()
    cursor = conn.cursor()
    lim = max(1, int(limit or 100))
    cursor.execute(
        f"""
        SELECT
            e.id,
            e.usuario_id,
            COALESCE(u.email, '') AS email_usuario,
            e.empresa_id,
            COALESCE(emp.nome, '') AS nome_empresa,
            COALESCE(e.nome_evento, '') AS nome_evento,
            COALESCE(e.timestamp_evento, '') AS timestamp_evento,
            COALESCE(e.metadados_json, '{{}}') AS metadados_json
        FROM eventos_produto e
        LEFT JOIN usuarios u ON u.id = e.usuario_id
        LEFT JOIN empresas emp ON emp.id = e.empresa_id
        ORDER BY {_sql_order_ts_desc("e.timestamp_evento")}, e.id DESC
        LIMIT ?
        """,
        (lim,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": int(r[0]),
            "usuario_id": int(r[1] or 0) if r[1] is not None else None,
            "email_usuario": str(r[2] or ""),
            "empresa_id": int(r[3] or 0) if r[3] is not None else None,
            "nome_empresa": str(r[4] or ""),
            "nome_evento": str(r[5] or ""),
            "timestamp_evento": str(r[6] or ""),
            "metadados_json": str(r[7] or "{}"),
        }
        for r in rows
    ]


def obter_perfil_na_empresa(usuario_id, empresa_id) -> str | None:
    """Retorna perfil ('admin'|'gestor'|'colaborador') ou None se não houver vínculo."""
    if usuario_id is None or empresa_id is None:
        return None
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT perfil FROM empresa_membros
        WHERE usuario_id = ? AND empresa_id = ?
        """,
        (int(usuario_id), int(empresa_id)),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    perfil = str(row[0] or "").strip().lower()
    return perfil if perfil in PERFIS_EQUIPE_VALIDOS else None


def listar_membros_empresa(empresa_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.id,
               COALESCE(NULLIF(TRIM(u.nome), ''), u.email) AS nome_exibicao,
               u.email,
               m.perfil,
               c.status,
               c.expira_em
        FROM empresa_membros m
        JOIN usuarios u ON u.id = m.usuario_id
        LEFT JOIN empresa_convites_primeiro_acesso c
          ON c.id = (
              SELECT c2.id
              FROM empresa_convites_primeiro_acesso c2
              WHERE c2.empresa_id = m.empresa_id
                AND c2.usuario_id = m.usuario_id
              ORDER BY c2.id DESC
              LIMIT 1
          )
        WHERE m.empresa_id = ?
        ORDER BY LOWER(nome_exibicao) ASC
        """,
        (int(empresa_id),),
    )
    rows = cursor.fetchall()
    conn.close()
    out = []
    agora = datetime.now()
    for r in rows:
        status_raw = str(r[4] or "").strip().lower()
        expira_raw = str(r[5] or "").strip()
        if status_raw == "pendente" and expira_raw:
            try:
                if datetime.strptime(expira_raw, "%Y-%m-%d %H:%M:%S") < agora:
                    status_raw = "expirado"
            except Exception:
                pass
        if status_raw == "pendente":
            status_visual = "🟡 Pendente"
        elif status_raw == "expirado":
            status_visual = "⚫ Expirado"
        else:
            status_visual = "🟢 Aceito"
            status_raw = "aceito"
        out.append(
            {
                "usuario_id": int(r[0]),
                "nome": r[1],
                "email": r[2],
                "perfil": str(r[3] or "").lower(),
                "status_convite": status_visual,
                "status_convite_raw": status_raw,
            }
        )
    return out


def contar_admins_empresa(empresa_id) -> int:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM empresa_membros
        WHERE empresa_id = ? AND LOWER(TRIM(perfil)) = 'admin'
        """,
        (int(empresa_id),),
    )
    n = int(cursor.fetchone()[0] or 0)
    conn.close()
    return n


def adicionar_ou_atualizar_membro_empresa(empresa_id, usuario_id_alvo, perfil: str):
    perfil = str(perfil or "").strip().lower()
    if perfil not in PERFIS_EQUIPE_VALIDOS:
        raise ValueError("Perfil inválido.")
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO empresa_membros (usuario_id, empresa_id, perfil, criado_em)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(usuario_id, empresa_id) DO UPDATE SET
            perfil = excluded.perfil
        """,
        (int(usuario_id_alvo), int(empresa_id), perfil, agora),
    )
    conn.commit()
    conn.close()


def atualizar_perfil_membro_empresa(empresa_id, usuario_id_alvo, novo_perfil: str):
    novo_perfil = str(novo_perfil or "").strip().lower()
    if novo_perfil not in PERFIS_EQUIPE_VALIDOS:
        raise ValueError("Perfil inválido.")
    atual = obter_perfil_na_empresa(usuario_id_alvo, empresa_id)
    if not atual:
        raise ValueError("Usuário não pertence a esta empresa.")
    if atual == "admin" and novo_perfil != "admin":
        if contar_admins_empresa(empresa_id) <= 1:
            raise ValueError("Não é possível remover o único administrador da empresa.")
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE empresa_membros SET perfil = ?
        WHERE empresa_id = ? AND usuario_id = ?
        """,
        (novo_perfil, int(empresa_id), int(usuario_id_alvo)),
    )
    conn.commit()
    conn.close()


def remover_membro_empresa(empresa_id, usuario_id_alvo):
    perfil = obter_perfil_na_empresa(usuario_id_alvo, empresa_id)
    if not perfil:
        return
    if perfil == "admin" and contar_admins_empresa(empresa_id) <= 1:
        raise ValueError("Não é possível remover o único administrador da empresa.")
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM empresa_membros
        WHERE empresa_id = ? AND usuario_id = ?
        """,
        (int(empresa_id), int(usuario_id_alvo)),
    )
    conn.commit()
    conn.close()


def _hash_token_convite_primeiro_acesso(token_plain: str) -> str:
    return hashlib.sha256(str(token_plain).encode("utf-8")).hexdigest()


def criar_ou_reenviar_convite_primeiro_acesso(
    empresa_id,
    nome_convite: str,
    email_convite: str,
    perfil: str,
    convidado_por_usuario_id,
    validade_horas=48,
) -> tuple[bool, str, str | None]:
    """
    Cria/renova convite com token de primeiro acesso. Nunca retorna senha.
    Retorna (ok, mensagem, token_plain_uso_unico ou None).
    """
    email_convite = (email_convite or "").strip().lower()
    nome_convite = (nome_convite or "").strip()
    perfil = str(perfil or "").strip().lower()
    if not email_convite:
        return False, "Informe um e-mail válido.", None
    if perfil not in PERFIS_EQUIPE_VALIDOS:
        return False, "Perfil inválido.", None

    uid_existente = obter_usuario_id_por_email(email_convite)
    try:
        if uid_existente:
            uid = uid_existente
            if nome_convite:
                atualizar_nome_usuario(uid, nome_convite)
        else:
            senha_placeholder = secrets.token_urlsafe(24)
            uid = criar_usuario(email_convite, senha_placeholder, nome=nome_convite or None)

        if obter_perfil_na_empresa(uid, empresa_id):
            return False, "Este usuário já pertence à empresa.", None

        token_plain = str(uuid.uuid4())
        token_hash = _hash_token_convite_primeiro_acesso(token_plain)
        agora_dt = datetime.now()
        expira_dt = agora_dt + timedelta(hours=max(1, int(validade_horas or 48)))
        agora = agora_dt.strftime("%Y-%m-%d %H:%M:%S")
        expira = expira_dt.strftime("%Y-%m-%d %H:%M:%S")

        conn = conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE empresa_convites_primeiro_acesso
            SET status = 'expirado'
            WHERE empresa_id = ? AND usuario_id = ? AND status = 'pendente'
            """,
            (int(empresa_id), int(uid)),
        )
        cursor.execute(
            """
            INSERT INTO empresa_convites_primeiro_acesso (
                empresa_id, usuario_id, email, nome_convidado, perfil,
                token_hash, status, convidado_por_usuario_id, criado_em, expira_em
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pendente', ?, ?, ?)
            """,
            (
                int(empresa_id),
                int(uid),
                email_convite,
                nome_convite or None,
                perfil,
                token_hash,
                int(convidado_por_usuario_id),
                agora,
                expira,
            ),
        )
        conn.commit()
        conn.close()
        return True, "Convite criado com sucesso.", token_plain
    except Exception as exc:
        return False, str(exc), None


def convidar_usuario_para_empresa(
    empresa_id,
    nome_convite: str,
    email_convite: str,
    perfil: str,
    convidado_por_usuario_id=None,
) -> tuple[bool, str, str | None]:
    """
    Compatibilidade: agora opera via convite seguro com token de primeiro acesso.
    """
    return criar_ou_reenviar_convite_primeiro_acesso(
        empresa_id=empresa_id,
        nome_convite=nome_convite,
        email_convite=email_convite,
        perfil=perfil,
        convidado_por_usuario_id=convidado_por_usuario_id or 0,
    )


def listar_convites_primeiro_acesso_empresa(empresa_id) -> list[dict]:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT c.id, c.email, c.nome_convidado, c.perfil, c.status, c.criado_em, c.expira_em, c.aceito_em
        FROM empresa_convites_primeiro_acesso c
        WHERE c.empresa_id = ?
        ORDER BY {_sql_order_ts_desc("c.criado_em")}, c.id DESC
        """,
        (int(empresa_id),),
    )
    rows = cursor.fetchall()
    conn.close()
    out = []
    agora = datetime.now()
    for row in rows:
        status = str(row[4] or "pendente")
        if status == "pendente":
            try:
                if datetime.strptime(str(row[6]), "%Y-%m-%d %H:%M:%S") < agora:
                    status = "expirado"
            except Exception:
                pass
        out.append(
            {
                "convite_id": int(row[0]),
                "email": str(row[1] or ""),
                "nome": str(row[2] or ""),
                "perfil": str(row[3] or ""),
                "status": status,
                "criado_em": str(row[5] or ""),
                "expira_em": str(row[6] or ""),
                "aceito_em": str(row[7] or ""),
            }
        )
    return out


def validar_token_convite_primeiro_acesso(token_plain: str) -> dict | None:
    if not token_plain or not str(token_plain).strip():
        return None
    token_hash = _hash_token_convite_primeiro_acesso(token_plain.strip())
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.id, c.empresa_id, c.usuario_id, c.email, c.nome_convidado, c.perfil, c.status, c.expira_em
        FROM empresa_convites_primeiro_acesso c
        WHERE c.token_hash = ?
        ORDER BY c.id DESC
        LIMIT 1
        """,
        (token_hash,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    status = str(row[6] or "").strip().lower()
    if status != "pendente":
        return None
    try:
        expira = datetime.strptime(str(row[7]), "%Y-%m-%d %H:%M:%S")
        if expira < datetime.now():
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE empresa_convites_primeiro_acesso SET status = 'expirado' WHERE id = ?",
                (int(row[0]),),
            )
            conn.commit()
            conn.close()
            return None
    except Exception:
        return None
    return {
        "convite_id": int(row[0]),
        "empresa_id": int(row[1]),
        "usuario_id": int(row[2]),
        "email": str(row[3] or ""),
        "nome_convidado": str(row[4] or ""),
        "perfil": str(row[5] or ""),
    }


def concluir_convite_primeiro_acesso(token_plain: str, nova_senha: str) -> tuple[bool, str]:
    convite = validar_token_convite_primeiro_acesso(token_plain)
    if not convite:
        return False, "Este link de convite é inválido ou expirou."
    usuario_id = int(convite["usuario_id"])
    empresa_id = int(convite["empresa_id"])
    perfil = str(convite["perfil"] or "").strip().lower()
    if perfil not in PERFIS_EQUIPE_VALIDOS:
        return False, "Perfil do convite inválido."
    try:
        atualizar_senha_usuario(usuario_id, nova_senha)
        adicionar_ou_atualizar_membro_empresa(empresa_id, usuario_id, perfil)
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE empresa_convites_primeiro_acesso
            SET status = 'aceito', aceito_em = ?
            WHERE id = ?
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(convite["convite_id"])),
        )
        conn.commit()
        conn.close()
        return True, "Convite aceito com sucesso. Faça login para continuar."
    except Exception as exc:
        return False, str(exc)


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


def definir_plano_usuario(usuario_id, plano, status="active", alterado_por="sistema"):
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    garantir_plano_usuario(usuario_id, plano_default=plano)
    cursor.execute(
        "SELECT id, plano, status FROM assinaturas WHERE usuario_id = ?",
        (int(usuario_id),),
    )
    row_atual = cursor.fetchone()
    assinatura_id = int(row_atual[0]) if row_atual else None
    plano_anterior = str(row_atual[1] or "FREE") if row_atual else "FREE"
    status_anterior = str(row_atual[2] or "active") if row_atual else "active"
    plano_novo = str(plano or "FREE").upper()
    status_novo = str(status or "active").lower()

    cursor.execute("""
    UPDATE assinaturas
    SET plano = ?, status = ?, updated_at = ?
    WHERE usuario_id = ?
    """, (plano_novo, status_novo, agora, usuario_id))

    conn.commit()
    conn.close()
    if (plano_anterior != plano_novo) or (status_anterior != status_novo):
        registrar_mudanca_plano_assinatura(
            assinatura_id=assinatura_id,
            usuario_id=int(usuario_id),
            plano_anterior=plano_anterior,
            plano_novo=plano_novo,
            status_anterior=status_anterior,
            status_novo=status_novo,
            alterado_por=str(alterado_por or "sistema"),
        )


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
    if IS_POSTGRES:
        cursor.execute(
            """
            INSERT INTO onboarding_usuario (
                usuario_id,
                etapa_atual,
                concluido,
                criado_em,
                atualizado_em
            )
            VALUES (?, 1, 0, ?, ?)
            ON CONFLICT (usuario_id) DO NOTHING
            """,
            (usuario_id, agora, agora),
        )
    else:
        cursor.execute(
            """
            INSERT OR IGNORE INTO onboarding_usuario (
                usuario_id,
                etapa_atual,
                concluido,
                criado_em,
                atualizado_em
            )
            VALUES (?, 1, 0, ?, ?)
            """,
            (usuario_id, agora, agora),
        )
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
    versao_ia="v1",
    criado_por_usuario_id=None,
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
        versao_ia,
        criado_por_usuario_id
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        empresa_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tipo_caso,
        risco,
        pontuacao,
        json.dumps(dados),
        json.dumps(resultado),
        json.dumps(parecer),
        versao_ia,
        int(criado_por_usuario_id) if criado_por_usuario_id is not None else None,
    ))

    aid = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    return aid


def criar_analise_stub_validacao_fatos(empresa_id, usuario_id) -> int:
    """Cria linha mínima em analises para FK de fatos validados (não entra em métricas de caso)."""
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO analises (
            empresa_id,
            data_analise,
            tipo_caso,
            risco,
            pontuacao,
            dados_json,
            resultado_json,
            parecer_json,
            versao_ia,
            criado_por_usuario_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(empresa_id),
            agora,
            TIPO_ANALISE_STUB_VALIDACAO_FATOS,
            "INCONCLUSIVO",
            0,
            json.dumps({"origem": "stub_validacao_fatos_documento"}),
            json.dumps({}),
            json.dumps({}),
            "stub_fatos",
            int(usuario_id),
        ),
    )
    aid = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    return aid


def substituir_fatos_validados(analise_id, usuario_id, linhas: list[tuple[str, str, str]]):
    """Substitui todas as linhas de fatos validados para uma análise."""
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uid = int(usuario_id)
    aid = int(analise_id)
    cursor.execute(
        "DELETE FROM analises_fatos_validados WHERE analise_id = ?",
        (aid,),
    )
    for nome_fato, valor_fato, fonte in linhas:
        cursor.execute(
            """
            INSERT INTO analises_fatos_validados (
                analise_id, nome_fato, valor_fato, fonte, validado_em, validado_por_usuario_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (aid, str(nome_fato), str(valor_fato), str(fonte), agora, uid),
        )
    conn.commit()
    conn.close()


def listar_fatos_validados(analise_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT nome_fato, valor_fato, fonte, validado_em, validado_por_usuario_id
        FROM analises_fatos_validados
        WHERE analise_id = ?
        ORDER BY LOWER(nome_fato) ASC
        """,
        (int(analise_id),),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "nome_fato": r[0],
            "valor_fato": r[1],
            "fonte": r[2],
            "validado_em": r[3],
            "validado_por_usuario_id": r[4],
        }
        for r in rows
    ]


def obter_mapa_fatos_validados(analise_id) -> dict[str, str]:
    """Mapa nome_fato → valor (uso futuro score_engine v2 — apenas fatos aprovados)."""
    out = {}
    for row in listar_fatos_validados(analise_id):
        out[str(row["nome_fato"])] = str(row["valor_fato"] or "")
    return out


def _hash_api_key_secreta(api_key_plain: str) -> str:
    """SHA-256 hex da chave — único valor persistido (nunca armazenar o segredo em texto puro)."""
    return hashlib.sha256(str(api_key_plain).encode("utf-8")).hexdigest()


def gerar_e_salvar_api_key(empresa_id) -> str:
    """
    Revoga chaves ativas da empresa, gera nova chave e persiste apenas o hash.
    Retorna o segredo em texto claro uma única vez para exibição ao administrador.
    """
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    eid = int(empresa_id)
    cursor.execute(
        """
        UPDATE empresa_api_keys SET revogada_em = ?
        WHERE empresa_id = ? AND revogada_em IS NULL
        """,
        (agora, eid),
    )
    plain = f"dpia_{secrets.token_urlsafe(32)}"
    digest = _hash_api_key_secreta(plain)
    cursor.execute(
        """
        INSERT INTO empresa_api_keys (empresa_id, api_key_hash, criada_em, revogada_em)
        VALUES (?, ?, ?, NULL)
        """,
        (eid, digest, agora),
    )
    conn.commit()
    conn.close()
    return plain


def revogar_api_key(empresa_id) -> int:
    """Marca todas as chaves ativas da empresa como revogadas. Retorna linhas afetadas."""
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        UPDATE empresa_api_keys SET revogada_em = ?
        WHERE empresa_id = ? AND revogada_em IS NULL
        """,
        (agora, int(empresa_id)),
    )
    n = cursor.rowcount if cursor.rowcount is not None else 0
    conn.commit()
    conn.close()
    return int(n)


def validar_api_key(api_key_fornecida) -> int | None:
    """
    Valida Bearer token contra hash armazenado.
    Retorna empresa_id se a chave existir e não estiver revogada; caso contrário None.
    """
    if api_key_fornecida is None:
        return None
    raw = str(api_key_fornecida).strip()
    if not raw:
        return None
    digest = _hash_api_key_secreta(raw)
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT empresa_id FROM empresa_api_keys
        WHERE api_key_hash = ? AND revogada_em IS NULL
        ORDER BY id DESC LIMIT 1
        """,
        (digest,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return int(row[0])


def obter_metadados_chave_api_ativa(empresa_id) -> dict | None:
    """Última chave não revogada da empresa (sem revelar segredo)."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, criada_em FROM empresa_api_keys
        WHERE empresa_id = ? AND revogada_em IS NULL
        ORDER BY id DESC LIMIT 1
        """,
        (int(empresa_id),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": int(row[0]), "criada_em": str(row[1] or "")}


def obter_ultima_sincronizacao_funcionarios(empresa_id) -> str | None:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT MAX(ultima_atualizacao) FROM empresa_funcionarios_integracao
        WHERE empresa_id = ?
        """,
        (int(empresa_id),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row or row[0] is None:
        return None
    return str(row[0])


def contar_funcionarios_integracao(empresa_id) -> int:
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) FROM empresa_funcionarios_integracao
        WHERE empresa_id = ?
        """,
        (int(empresa_id),),
    )
    row = cursor.fetchone()
    conn.close()
    return int(row[0] or 0) if row else 0


def listar_funcionarios_integracao(empresa_id) -> list[dict]:
    """Todos os registros de funcionários sincronizados para a empresa (auditoria em massa)."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, empresa_id, employee_id_externo, nome_completo, data_admissao,
               cargo, salario_bruto, tipo_contrato, ultima_atualizacao
        FROM empresa_funcionarios_integracao
        WHERE empresa_id = ?
        ORDER BY LOWER(nome_completo) ASC
        """,
        (int(empresa_id),),
    )
    cols = [
        "id",
        "empresa_id",
        "employee_id_externo",
        "nome_completo",
        "data_admissao",
        "cargo",
        "salario_bruto",
        "tipo_contrato",
        "ultima_atualizacao",
    ]
    out = []
    for row in cursor.fetchall():
        out.append({cols[i]: row[i] for i in range(len(cols))})
    conn.close()
    return out


def salvar_auditoria_risco_massa(empresa_id, executada_por_usuario_id, resultado: dict) -> int:
    """Persiste snapshot JSON da auditoria. Retorna id da linha inserida."""
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = json.dumps(resultado, ensure_ascii=False)
    cursor.execute(
        """
        INSERT INTO empresa_auditorias_risco (
            empresa_id, executada_em, executada_por_usuario_id, resultado_json
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            int(empresa_id),
            agora,
            int(executada_por_usuario_id or 0),
            payload,
        ),
    )
    rid = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    return rid


def obter_ultima_auditoria_risco_massa(empresa_id) -> dict | None:
    """Última auditoria gravada para a empresa, ou None."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT id, executada_em, executada_por_usuario_id, resultado_json
        FROM empresa_auditorias_risco
        WHERE empresa_id = ?
        ORDER BY {_sql_order_ts_desc("executada_em")}, id DESC
        LIMIT 1
        """,
        (int(empresa_id),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    raw_json = row[3]
    try:
        resultado = json.loads(raw_json) if raw_json else {}
    except json.JSONDecodeError:
        resultado = {}
    return {
        "id": int(row[0]),
        "executada_em": str(row[1] or ""),
        "executada_por_usuario_id": int(row[2] or 0),
        "resultado": resultado if isinstance(resultado, dict) else {},
    }


def upsert_funcionarios_integracao_lote(empresa_id, employees: list) -> int:
    """
    Insere ou atualiza funcionários por employee_id_externo (uso pelo endpoint REST futuro).
    Ignora entradas sem employee_id_externo. Retorna quantidade processada.
    """
    if not employees:
        return 0
    conn = conectar()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    eid = int(empresa_id)
    n = 0
    for raw in employees:
        if not isinstance(raw, dict):
            continue
        ext_id = str(raw.get("employee_id_externo") or "").strip()
        if not ext_id:
            continue
        nome = str(raw.get("nome_completo") or "").strip() or "(sem nome)"
        adm = raw.get("data_admissao")
        data_adm = None if adm is None else str(adm).strip() or None
        cargo = raw.get("cargo")
        cargo_s = None if cargo is None else str(cargo).strip() or None
        sal = raw.get("salario_bruto")
        try:
            salario = float(sal) if sal is not None and str(sal).strip() != "" else None
        except (TypeError, ValueError):
            salario = None
        tipo = raw.get("tipo_contrato")
        tipo_s = None if tipo is None else str(tipo).strip() or None
        cursor.execute(
            """
            INSERT INTO empresa_funcionarios_integracao (
                empresa_id, employee_id_externo, nome_completo, data_admissao,
                cargo, salario_bruto, tipo_contrato, ultima_atualizacao
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(empresa_id, employee_id_externo) DO UPDATE SET
                nome_completo = excluded.nome_completo,
                data_admissao = excluded.data_admissao,
                cargo = excluded.cargo,
                salario_bruto = excluded.salario_bruto,
                tipo_contrato = excluded.tipo_contrato,
                ultima_atualizacao = excluded.ultima_atualizacao
            """,
            (eid, ext_id, nome, data_adm, cargo_s, salario, tipo_s, agora),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def rotulo_tipo_caso_para_exibicao(tipo_raw: object) -> str:
    """Converte identificador interno gravado em analises.tipo_caso em texto para o usuário final."""
    t = str(tipo_raw or "").strip().lower().replace("-", "_")
    if not t:
        return "Registros de análises trabalhistas"
    mapa = {
        "consultoria_conversa": "Análise de Risco Trabalhista",
        "validacao_fatos_documento": "Validação de fatos em documento anexado",
        "duvida_geral": "Dúvidas gerais trabalhistas",
        "rescisao": "Rescisão ou desligamento",
        "pedido_demissao": "Pedido de demissão",
        "terceirizacao": "Terceirização",
        "assedio": "Assédio moral ou sexual",
        "jornada": "Jornada de trabalho ou horas extras",
        "afastamento": "Afastamento ou licença",
        "acidente_trabalho": "Acidente de trabalho ou saúde ocupacional",
        "atestado": "Afastamentos médicos ou atestados",
        "burnout": "Saúde mental e burnout",
        "salario": "Salários, adicionais e verbas rescisórias",
        # Evita eco de nomes falsos vindos da classificação
        "não_classificado": "Registros diversos trabalhistas",
        "nao_classificado": "Registros diversos trabalhistas",
        "não classificado": "Registros diversos trabalhistas",
    }
    if t in mapa:
        return mapa[t]
    # valores legados já em português (sem snake_case típico)
    if "_" not in t:
        cand = str(tipo_raw or "").strip()
        if cand and cand != TIPO_ANALISE_STUB_VALIDACAO_FATOS:
            return cand[:120] + ("..." if len(cand) > 120 else "")
    return "Análises trabalhistas registradas"


def obter_historico_empresa(empresa_id, limite=20, criado_por_usuario_id=None):
    conn = conectar()
    cursor = conn.cursor()
    if criado_por_usuario_id is not None:
        cursor.execute(
            f"""
            SELECT tipo_caso, risco, data_analise
            FROM analises
            WHERE empresa_id = ?
              AND COALESCE(criado_por_usuario_id, -1) = ?
              AND COALESCE(tipo_caso, '') != ?
            ORDER BY {_sql_order_ts_desc("data_analise")}
            LIMIT ?
            """,
            (
                empresa_id,
                int(criado_por_usuario_id),
                TIPO_ANALISE_STUB_VALIDACAO_FATOS,
                int(limite),
            ),
        )
    else:
        cursor.execute(
            f"""
            SELECT tipo_caso, risco, data_analise
            FROM analises
            WHERE empresa_id = ?
              AND COALESCE(tipo_caso, '') != ?
            ORDER BY {_sql_order_ts_desc("data_analise")}
            LIMIT ?
            """,
            (empresa_id, TIPO_ANALISE_STUB_VALIDACAO_FATOS, int(limite)),
        )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {
            "total_ocorrencias": 0,
            "tipos_frequentes": [],
            "riscos_frequentes": [],
            "resumo": "",
        }

    contagem_tipos = {}
    contagem_riscos = {}
    for tipo_caso, risco, _ in rows:
        tipo_key = str(tipo_caso or "não_classificado")
        risco_key = str(risco or "INCONCLUSIVO").upper()
        contagem_tipos[tipo_key] = contagem_tipos.get(tipo_key, 0) + 1
        contagem_riscos[risco_key] = contagem_riscos.get(risco_key, 0) + 1

    tipos_frequentes = sorted(contagem_tipos.items(), key=lambda x: x[1], reverse=True)
    riscos_frequentes = sorted(contagem_riscos.items(), key=lambda x: x[1], reverse=True)
    n = len(rows)
    tipo_principal = tipos_frequentes[0][0]
    qtd_principal = int(tipos_frequentes[0][1])
    lab = rotulo_tipo_caso_para_exibicao(tipo_principal)
    if len(tipos_frequentes) == 1:
        resumo = f"A empresa possui {n} registro(s) de {lab} no sistema."
    elif qtd_principal == n:
        resumo = f"A empresa possui {n} registro(s) de {lab} no sistema."
    else:
        resumo = (
            f"A empresa possui {n} análise(s) anteriores registradas no sistema "
            f"({qtd_principal} relacionadas a {lab})."
        )

    tipos_frequentes_exibicao = [
        (rotulo_tipo_caso_para_exibicao(tipo), int(qtd))
        for tipo, qtd in tipos_frequentes
    ]

    return {
        "total_ocorrencias": len(rows),
        "tipos_frequentes": tipos_frequentes,
        "tipos_frequentes_exibicao": tipos_frequentes_exibicao,
        "riscos_frequentes": riscos_frequentes,
        "resumo": resumo,
    }


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
def _sql_ts_gte_days_ago(col_expr: str, days: int) -> str:
    """Predicado: coluna de data/hora nos últimos N dias (SQLite ou Postgres)."""
    n = int(days)
    if IS_POSTGRES:
        return f"CAST({col_expr} AS timestamp) >= NOW() - INTERVAL '{n} days'"
    return f"date({col_expr}) >= date('now', '-{n} days')"


def _sql_ts_in_range_days_ago(col_expr: str, start_days: int, end_days: int) -> str:
    """Janela [now-start_days, now-end_days) em dias."""
    s, e = int(start_days), int(end_days)
    if IS_POSTGRES:
        return (
            f"CAST({col_expr} AS timestamp) >= NOW() - INTERVAL '{s} days' "
            f"AND CAST({col_expr} AS timestamp) < NOW() - INTERVAL '{e} days'"
        )
    return (
        f"date({col_expr}) >= date('now', '-{s} days') "
        f"AND date({col_expr}) < date('now', '-{e} days')"
    )


def _sql_date_is_today(col_expr: str) -> str:
    if IS_POSTGRES:
        return f"CAST({col_expr} AS date) = CURRENT_DATE"
    return f"date({col_expr}) = date('now')"


def _sql_ym_equals(col_expr: str) -> str:
    """Comparar ano-mês (placeholder ? = YYYY-MM)."""
    if IS_POSTGRES:
        return f"to_char(CAST({col_expr} AS timestamp), 'YYYY-MM') = ?"
    return f"strftime('%Y-%m', {col_expr}) = ?"


def _sql_day_expr(col_expr: str) -> str:
    """Truncar para dia (SELECT / GROUP BY)."""
    if IS_POSTGRES:
        return f"CAST({col_expr} AS date)"
    return f"date({col_expr})"


def _sql_ym_expr(col_expr: str) -> str:
    if IS_POSTGRES:
        return f"to_char(CAST({col_expr} AS timestamp), 'YYYY-MM')"
    return f"strftime('%Y-%m', {col_expr})"


def _sql_order_ts_desc(col_expr: str) -> str:
    if IS_POSTGRES:
        return f"CAST({col_expr} AS timestamp) DESC"
    return f"datetime({col_expr}) DESC"


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
        f"""
        SELECT COUNT(DISTINCT e.usuario_id)
        FROM analises a
        INNER JOIN empresas e ON e.id = a.empresa_id
        WHERE {_sql_ts_gte_days_ago('a.data_analise', 7)}
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
        f"""
        SELECT id, nome, empresa, email, whatsapp, plano_interesse, criado_em,
               COALESCE(status, 'novo')
        FROM leads
        ORDER BY {_sql_order_ts_desc("criado_em")}
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
    ordem = _sql_order_ts_desc("COALESCE(atualizado_em, criado_em)")
    if filtro_status and filtro_status in LEAD_CRM_STATUSES:
        cursor.execute(
            base + f" WHERE COALESCE(status, 'novo') = ? ORDER BY {ordem}",
            (filtro_status,),
        )
    else:
        cursor.execute(base + f" ORDER BY {ordem}")
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
        f"SELECT COUNT(*) FROM leads WHERE {_sql_date_is_today('criado_em')}"
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
        f"""
        SELECT COUNT(*) FROM leads
        WHERE status = 'cliente_fechado'
          AND {_sql_ym_equals('COALESCE(atualizado_em, criado_em)')}
        """,
        (ym,),
    )
    fechados_mes = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        f"""
        SELECT COUNT(*) FROM leads
        WHERE status = 'perdido'
          AND {_sql_ym_equals('COALESCE(atualizado_em, criado_em)')}
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
    day = _sql_day_expr("created_at")
    cursor.execute(
        f"""
        SELECT {day} AS d, COUNT(*)
        FROM assinaturas
        WHERE created_at IS NOT NULL
          AND {_sql_ts_gte_days_ago('created_at', 30)}
        GROUP BY {day}
        ORDER BY d
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def admin_series_leads_30_dias():
    conn = conectar()
    cursor = conn.cursor()
    day = _sql_day_expr("criado_em")
    cursor.execute(
        f"""
        SELECT {day} AS d, COUNT(*)
        FROM leads
        WHERE criado_em IS NOT NULL
          AND {_sql_ts_gte_days_ago('criado_em', 30)}
        GROUP BY {day}
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


def admin_listar_todos_usuarios_catalogo() -> list[dict]:
    """
    Catálogo global de usuários para Super Admin.
    Inclui nome, e-mail, data de cadastro (referência), status e plano.
    """
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            u.id,
            COALESCE(NULLIF(TRIM(u.nome), ''), '') AS nome,
            COALESCE(u.email, '') AS email,
            COALESCE(
                (SELECT MIN(created_at) FROM assinaturas a WHERE a.usuario_id = u.id),
                ''
            ) AS data_cadastro,
            COALESCE(u.bloqueado, 0) AS bloqueado,
            COALESCE(s.plano, 'FREE') AS plano,
            COALESCE(s.status, 'active') AS status_assinatura
        FROM usuarios u
        LEFT JOIN assinaturas s ON s.usuario_id = u.id
        ORDER BY u.id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    out = []
    for r in rows:
        bloqueado = int(r[4] or 0) == 1
        status_assin = str(r[6] or "active").lower()
        if bloqueado:
            status_usuario = "Bloqueado"
        elif status_assin == "suspended":
            status_usuario = "Suspenso"
        else:
            status_usuario = "Ativo"
        out.append(
            {
                "id_usuario": int(r[0]),
                "nome": str(r[1] or ""),
                "email": str(r[2] or ""),
                "data_cadastro": str(r[3] or ""),
                "status_usuario": status_usuario,
                "plano_atual": str(r[5] or "FREE"),
            }
        )
    return out


def admin_definir_bloqueio_usuario(usuario_id, bloqueado: int, actor_admin_id=None) -> bool:
    if int(bloqueado) == 1 and _email_admin_master(obter_email_usuario(usuario_id)):
        return False
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(bloqueado, 0) FROM usuarios WHERE id = ?",
        (int(usuario_id),),
    )
    row_b = cursor.fetchone()
    anterior_bloqueado = int(row_b[0] or 0) if row_b else 0
    novo_bloqueado = 1 if int(bloqueado) else 0
    cursor.execute(
        "UPDATE usuarios SET bloqueado = ? WHERE id = ?",
        (novo_bloqueado, int(usuario_id)),
    )
    conn.commit()
    conn.close()
    if anterior_bloqueado != novo_bloqueado:
        registrar_mudanca_status_usuario(
            usuario_id=int(usuario_id),
            status_anterior="bloqueado" if anterior_bloqueado else "ativo",
            status_novo="bloqueado" if novo_bloqueado else "ativo",
            alterado_por="superadmin",
            motivo="admin_definir_bloqueio_usuario",
        )
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
    definir_plano_usuario(
        int(usuario_id),
        plano,
        status=status_assinatura,
        alterado_por="superadmin",
    )
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
          AND {_sql_ym_equals('COALESCE(updated_at, created_at)')}
        """,
        (ym,),
    )
    upgrades_mes = int(cursor.fetchone()[0] or 0)

    cursor.execute(
        f"""
        SELECT COUNT(*) FROM assinaturas a
        WHERE UPPER(COALESCE(a.plano, 'FREE')) = 'FREE'
          AND COALESCE(a.status, 'active') = 'active'
          AND {_sql_ym_equals('COALESCE(a.updated_at, a.created_at)')}
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
        f"""
        SELECT COUNT(*) FROM assinaturas
        WHERE LOWER(COALESCE(status, '')) = 'suspended'
          AND {_sql_ym_equals('COALESCE(updated_at, created_at)')}
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
    ym_col = _sql_ym_expr("COALESCE(updated_at, created_at)")
    cursor.execute(
        f"""
        SELECT {ym_col} AS ym,
               SUM(COALESCE(valor, 0))
        FROM checkout_transacoes
        WHERE {_checkout_pago_sql()}
          AND {_sql_ts_gte_days_ago('COALESCE(updated_at, created_at)', 200)}
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
        ORDER BY {_sql_order_ts_desc('COALESCE(c.updated_at, c.created_at)')}
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
        ORDER BY {_sql_order_ts_desc('COALESCE(a.updated_at, a.created_at)')}
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
        f"""
        SELECT COUNT(*) FROM leads
        WHERE {_sql_ts_gte_days_ago('criado_em', 7)}
        """
    )
    leads_curr = int(c.fetchone()[0] or 0)
    c.execute(
        f"""
        SELECT COUNT(*) FROM leads
        WHERE {_sql_ts_in_range_days_ago('criado_em', 14, 7)}
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

    ts_sub = "COALESCE(updated_at, created_at)"
    c.execute(
        f"""
        SELECT COUNT(*) FROM assinaturas
        WHERE LOWER(COALESCE(status, '')) = 'suspended'
          AND {_sql_ts_gte_days_ago(ts_sub, 7)}
        """
    )
    susp_curr = int(c.fetchone()[0] or 0)
    c.execute(
        f"""
        SELECT COUNT(*) FROM assinaturas
        WHERE LOWER(COALESCE(status, '')) = 'suspended'
          AND {_sql_ts_in_range_days_ago(ts_sub, 14, 7)}
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
          AND {_sql_ts_gte_days_ago(ts_sub, 30)}
        """
    )
    rev_curr = float(c.fetchone()[0] or 0)
    c.execute(
        f"""
        SELECT COALESCE(SUM(valor), 0) FROM checkout_transacoes
        WHERE {_checkout_pago_sql()}
          AND {_sql_ts_in_range_days_ago(ts_sub, 60, 30)}
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
        f"""
        SELECT COUNT(DISTINCT a.usuario_id)
        FROM assinaturas a
        WHERE COALESCE(a.status, 'active') = 'active'
          AND UPPER(COALESCE(a.plano, 'FREE')) IN ('PRO', 'PREMIUM')
          AND NOT EXISTS (
            SELECT 1 FROM analises an
            INNER JOIN empresas e ON e.id = an.empresa_id AND e.usuario_id = a.usuario_id
            WHERE {_sql_ts_gte_days_ago('an.data_analise', 14)}
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