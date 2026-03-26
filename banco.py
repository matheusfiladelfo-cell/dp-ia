import sqlite3
from datetime import datetime
import json
import bcrypt

DB_NAME = "dpia.db"


def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


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

    conn.commit()
    conn.close()


# =========================
# 🔐 USUÁRIOS (SEGURO)
# =========================

def criar_usuario(email, senha):
    conn = conectar()
    cursor = conn.cursor()

    senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())

    cursor.execute("""
    INSERT INTO usuarios (email, senha_hash)
    VALUES (?, ?)
    """, (email, senha_hash))

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