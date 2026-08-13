import sqlite3

from config import DATABASE_NAME


# =========================================================
# CONEXÃO
# =========================================================

def conectar():
    return sqlite3.connect(DATABASE_NAME)


# =========================================================
# CRIAR TABELAS
# =========================================================

def criar_tabelas():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contas_codigo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servico TEXT NOT NULL,
            apelido TEXT NOT NULL,
            provedor TEXT NOT NULL,
            email TEXT NOT NULL,
            senha_app TEXT,
            remetentes TEXT,
            ativa INTEGER DEFAULT 1,
            criado_em TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos_codigo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conta_id INTEGER NOT NULL,
            cliente_id INTEGER NOT NULL,
            atendido INTEGER DEFAULT 0,
            criado_em TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# CONTAS DE CÓDIGO - CRUD
# =========================================================

def cadastrar_conta_codigo(
    servico,
    apelido,
    provedor,
    email,
    senha_app,
    remetentes,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO contas_codigo
        (
            servico,
            apelido,
            provedor,
            email,
            senha_app,
            remetentes
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        servico,
        apelido,
        provedor,
        email,
        senha_app,
        remetentes,
    ))

    conta_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return conta_id


def listar_servicos_codigo():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT servico
        FROM contas_codigo
        WHERE ativa = 1
        ORDER BY servico
    """)

    resultados = cursor.fetchall()

    conn.close()

    return [linha[0] for linha in resultados]


def listar_contas_por_servico(
    servico,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            apelido,
            provedor
        FROM contas_codigo
        WHERE servico = ?
        AND ativa = 1
        ORDER BY apelido
    """, (
        servico,
    ))

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def listar_todas_contas_codigo():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            servico,
            apelido,
            provedor,
            ativa
        FROM contas_codigo
        ORDER BY servico, apelido
    """)

    resultados = cursor.fetchall()

    conn.close()

    return resultados


def buscar_conta_codigo(
    conta_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            servico,
            apelido,
            provedor,
            email,
            senha_app,
            remetentes,
            ativa
        FROM contas_codigo
        WHERE id = ?
    """, (
        conta_id,
    ))

    resultado = cursor.fetchone()

    conn.close()

    return resultado


CAMPOS_EDITAVEIS = {
    "servico": "servico",
    "apelido": "apelido",
    "email": "email",
    "senha_app": "senha_app",
    "remetentes": "remetentes",
}


def atualizar_campo_conta_codigo(
    conta_id,
    campo,
    valor,
):

    if campo not in CAMPOS_EDITAVEIS:
        raise ValueError(
            f"Campo inválido: {campo}"
        )

    coluna = CAMPOS_EDITAVEIS[campo]

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        f"""
        UPDATE contas_codigo
        SET {coluna} = ?
        WHERE id = ?
        """,
        (
            valor,
            conta_id,
        ),
    )

    alterado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return alterado


def definir_ativa_conta_codigo(
    conta_id,
    ativa,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE contas_codigo
        SET ativa = ?
        WHERE id = ?
    """, (
        1 if ativa else 0,
        conta_id,
    ))

    alterado = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return alterado


def excluir_conta_codigo(
    conta_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM contas_codigo
        WHERE id = ?
    """, (
        conta_id,
    ))

    excluido = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return excluido


# =========================================================
# PEDIDOS DE CÓDIGO MANUAL (PROTON)
# =========================================================

def criar_pedido_codigo(
    conta_id,
    cliente_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO pedidos_codigo
        (
            conta_id,
            cliente_id
        )
        VALUES (?, ?)
    """, (
        conta_id,
        cliente_id,
    ))

    pedido_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return pedido_id


def marcar_pedido_atendido(
    pedido_id,
):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pedidos_codigo
        SET atendido = 1
        WHERE id = ?
    """, (
        pedido_id,
    ))

    conn.commit()
    conn.close()
