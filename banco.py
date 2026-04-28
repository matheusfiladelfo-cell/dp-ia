import sqlite3
from datetime import datetime
import json
import bcrypt

# 🔥 PADRÃO ÚNICO DE BANCO (CRÍTICO)
DB_NAME = "dpia.db"


# =========================
# CONEXÃO CENTRALIZADA
# =========================
def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


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

    conn.commit()
    conn.close()


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

    cursor.execute("""
    SELECT id, senha_hash FROM usuarios
    WHERE email = ?
    """, (email,))

    user = cursor.fetchone()
    conn.close()

    if not user:
        return None

    user_id, senha_hash = user

    if bcrypt.checkpw(senha.encode(), senha_hash):
        return user_id

    return None


def obter_email_usuario(usuario_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


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