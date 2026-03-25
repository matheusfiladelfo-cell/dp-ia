import sqlite3
from datetime import datetime

# 🔥 PADRÃO ÚNICO
DB_NAME = "dpia.db"


def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # EMPRESAS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS empresas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cnpj TEXT,
        cidade TEXT,
        estado TEXT,
        data_cadastro TEXT
    )
    """)

    # FUNCIONÁRIOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS funcionarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER,
        nome TEXT NOT NULL,
        cpf TEXT,
        cargo TEXT,
        data_admissao TEXT,
        FOREIGN KEY (empresa_id) REFERENCES empresas(id)
    )
    """)

    # ANÁLISES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS analises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa_id INTEGER,
        funcionario_id INTEGER,
        data_analise TEXT,
        risco TEXT,  -- 🔥 PADRONIZADO
        detalhes TEXT,
        FOREIGN KEY (empresa_id) REFERENCES empresas(id),
        FOREIGN KEY (funcionario_id) REFERENCES funcionarios(id)
    )
    """)

    conn.commit()
    conn.close()


# ---------------- EMPRESAS ----------------

def cadastrar_empresa(nome, cnpj, cidade, estado):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO empresas (nome, cnpj, cidade, estado, data_cadastro)
    VALUES (?, ?, ?, ?, ?)
    """, (
        nome,
        cnpj,
        cidade,
        estado,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def listar_empresas():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM empresas ORDER BY nome ASC")
    dados = cursor.fetchall()
    conn.close()
    return dados


# ---------------- FUNCIONÁRIOS ----------------

def cadastrar_funcionario(empresa_id, nome, cpf, cargo, data_admissao):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO funcionarios (empresa_id, nome, cpf, cargo, data_admissao)
    VALUES (?, ?, ?, ?, ?)
    """, (
        empresa_id,
        nome,
        cpf,
        cargo,
        data_admissao
    ))

    conn.commit()
    conn.close()


def listar_funcionarios(empresa_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, nome FROM funcionarios
    WHERE empresa_id = ?
    ORDER BY nome ASC
    """, (empresa_id,))

    dados = cursor.fetchall()
    conn.close()
    return dados


# ---------------- ANÁLISES ----------------

def salvar_analise(empresa_id, funcionario_id, risco, detalhes):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO analises (empresa_id, funcionario_id, data_analise, risco, detalhes)
    VALUES (?, ?, ?, ?, ?)
    """, (
        empresa_id,
        funcionario_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        risco,
        detalhes
    ))

    conn.commit()
    conn.close()


def listar_analises_por_funcionario(funcionario_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, data_analise, risco, detalhes
    FROM analises
    WHERE funcionario_id = ?
    ORDER BY id DESC
    """, (funcionario_id,))

    dados = cursor.fetchall()
    conn.close()
    return dados