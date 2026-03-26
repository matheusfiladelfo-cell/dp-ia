import hashlib
from banco import conectar


def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


def cadastrar_usuario(email, senha):
    conn = conectar()
    cursor = conn.cursor()

    senha_hash = hash_senha(senha)

    try:
        cursor.execute("""
        INSERT INTO usuarios (email, senha_hash)
        VALUES (?, ?)
        """, (email, senha_hash))

        conn.commit()
        return True

    except:
        return False

    finally:
        conn.close()


def autenticar_usuario(email, senha):
    conn = conectar()
    cursor = conn.cursor()

    senha_hash = hash_senha(senha)

    cursor.execute("""
    SELECT id FROM usuarios
    WHERE email = ? AND senha_hash = ?
    """, (email, senha_hash))

    user = cursor.fetchone()
    conn.close()

    return user[0] if user else None