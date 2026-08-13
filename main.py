import re
import imaplib
import email

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    verificar_configuracao,
)

from database import (
    criar_tabelas,
    cadastrar_conta_codigo,
    listar_servicos_codigo,
    listar_contas_por_servico,
    listar_todas_contas_codigo,
    buscar_conta_codigo,
    atualizar_campo_conta_codigo,
    definir_ativa_conta_codigo,
    excluir_conta_codigo,
    criar_pedido_codigo,
    marcar_pedido_atendido,
)


# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

IMAP_HOSTS = {
    "gmail": ("imap.gmail.com", 993),
    "outlook": ("outlook.office365.com", 993),
}

PROVEDORES_AUTOMATICOS = ("gmail", "outlook")
PROVEDORES_MANUAIS = ("proton",)

CAMPOS_CADASTRO = [
    ("servico", "📺 Nome do serviço (ex: Netflix, Disney+, HBO Max)"),
    ("apelido", "🏷️ Apelido pra identificar essa conta (ex: Netflix #1)"),
    ("provedor", "📧 Provedor de email — digite exatamente: `gmail`, `outlook` ou `proton`"),
    ("email", "✉️ Email completo da conta"),
    ("senha_app", "🔑 Senha de app do email (pra gmail/outlook — se for proton, envie \"pular\")"),
    ("remetentes", "📨 Remetentes dos emails de código, separados por vírgula (ex: netflix.com, account.netflix.com) — ou envie \"pular\" pra pegar qualquer email recente"),
]


def is_admin(user_id):
    try:
        return int(user_id) == int(ADMIN_ID)
    except (ValueError, TypeError):
        return False


# =========================================================
# EXTRAÇÃO DE CÓDIGO/LINK DO EMAIL
# =========================================================

def extrair_corpo(msg):

    if msg.is_multipart():

        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(
                        decode=True
                    ).decode(errors="ignore")
                except Exception:
                    continue

        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    html = part.get_payload(
                        decode=True
                    ).decode(errors="ignore")
                    return re.sub(
                        "<[^<]+?>", " ", html
                    )
                except Exception:
                    continue

        return ""

    try:
        return msg.get_payload(
            decode=True
        ).decode(errors="ignore")
    except Exception:
        return ""


def extrair_codigo(texto):
    match = re.search(r"\b(\d{4,8})\b", texto)
    return match.group(1) if match else None


def extrair_link(texto):
    match = re.search(r"https?://\S+", texto)
    if match:
        return match.group(0).rstrip(
            ".,)\"'"
        )
    return None


def buscar_codigo_imap(
    provedor,
    email_conta,
    senha_app,
    remetentes,
):

    host_porta = IMAP_HOSTS.get(provedor)

    if not host_porta:
        return {
            "erro": "Provedor não suportado "
            "pra busca automática.",
        }

    host, porta = host_porta

    try:
        imap = imaplib.IMAP4_SSL(host, porta)
        imap.login(email_conta, senha_app)
        imap.select("INBOX")

        lista_remetentes = [
            r.strip()
            for r in (remetentes or "").split(",")
            if r.strip()
        ]

        status, dados = imap.search(None, "ALL")

        if status != "OK":
            imap.logout()
            return {
                "erro": "Não consegui acessar a "
                "caixa de entrada.",
            }

        ids = dados[0].split()
        ids = ids[-20:]

        mensagem_encontrada = None

        for msg_id in reversed(ids):

            status, msg_data = imap.fetch(
                msg_id, "(RFC822)"
            )

            if status != "OK" or not msg_data[0]:
                continue

            msg = email.message_from_bytes(
                msg_data[0][1]
            )

            remetente = msg.get("From", "")

            if lista_remetentes:
                if not any(
                    r.lower() in remetente.lower()
                    for r in lista_remetentes
                ):
                    continue

            mensagem_encontrada = msg
            break

        imap.logout()

        if not mensagem_encontrada:
            return {
                "erro": "Nenhum email recente "
                "encontrado. Peça um novo código "
                "no app do serviço e tente de "
                "novo em cerca de 1 minuto.",
            }

        corpo = extrair_corpo(mensagem_encontrada)
        codigo = extrair_codigo(corpo)
        link = extrair_link(corpo)
        assunto = mensagem_encontrada.get(
            "Subject", ""
        )

        return {
            "codigo": codigo,
            "link": link,
            "assunto": assunto,
            "resumo": corpo.strip()[:400],
        }

    except imaplib.IMAP4.error as erro:
        print("ERRO IMAP (login/protocolo):", repr(erro))
        return {
            "erro": "Não consegui entrar nesse "
            "email. Confirme a senha de app.",
        }

    except Exception as erro:
        print("ERRO IMAP (geral):", repr(erro))
        return {
            "erro": "Erro inesperado ao buscar "
            "o código. Tente de novo em instantes.",
        }


# =========================================================
# START / MENU
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    if update.message:
        await update.message.reply_text(
            "🔑 *BOT DE CÓDIGOS*\n\n"
            "Escolha o serviço que você precisa "
            "do código de acesso:",
            reply_markup=menu_principal(),
            parse_mode="Markdown",
        )


def menu_principal():

    botoes = [
        [
            InlineKeyboardButton(
                "🔑 PEGAR CÓDIGO",
                callback_data="pegar_codigo",
            )
        ],
    ]

    return InlineKeyboardMarkup(botoes)


def menu_admin():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ NOVA CONTA",
                    callback_data="admnova",
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 LISTAR CONTAS",
                    callback_data="admlistar",
                )
            ],
        ]
    )


async def comando_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    usuario = update.effective_user

    if not usuario or not is_admin(usuario.id):
        if update.message:
            await update.message.reply_text(
                "❌ Acesso negado."
            )
        return

    context.user_data.clear()

    if update.message:
        await update.message.reply_text(
            "👑 *PAINEL ADMIN*\n\n"
            "Gerencie as contas de código:",
            reply_markup=menu_admin(),
            parse_mode="Markdown",
        )


# =========================================================
# CLIENTE: ESCOLHER SERVIÇO / CONTA
# =========================================================

async def mostrar_lista_servicos(
    query,
):
    servicos = listar_servicos_codigo()

    if not servicos:
        await query.edit_message_text(
            "❌ Nenhum serviço disponível no "
            "momento."
        )
        return

    botoes = []

    for indice, servico in enumerate(servicos):
        botoes.append(
            [
                InlineKeyboardButton(
                    f"📺 {servico}",
                    callback_data=(
                        f"servico_{indice}"
                    ),
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "🏠 Menu",
                callback_data="menu",
            )
        ]
    )

    await query.edit_message_text(
        "🔑 *PEGAR CÓDIGO*\n\n"
        "Escolha o serviço:",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


async def mostrar_contas_do_servico(
    query,
    context,
    indice_servico,
):
    servicos = listar_servicos_codigo()

    try:
        servico = servicos[indice_servico]
    except IndexError:
        await query.answer(
            "❌ Serviço inválido.",
            show_alert=True,
        )
        return

    contas = listar_contas_por_servico(servico)

    if not contas:
        await query.answer(
            "❌ Nenhuma conta ativa pra esse "
            "serviço.",
            show_alert=True,
        )
        return

    if len(contas) == 1:
        await processar_pedido_codigo(
            query,
            context,
            contas[0][0],
        )
        return

    botoes = []

    for conta_id, apelido, _provedor in contas:
        botoes.append(
            [
                InlineKeyboardButton(
                    f"🔑 {apelido}",
                    callback_data=(
                        f"buscarconta_{conta_id}"
                    ),
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "⬅️ Voltar",
                callback_data="pegar_codigo",
            )
        ]
    )

    await query.edit_message_text(
        f"🔑 *{servico}*\n\n"
        "Qual conta você quer o código?",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


# =========================================================
# PROCESSAR PEDIDO DE CÓDIGO
# =========================================================

async def processar_pedido_codigo(
    query,
    context,
    conta_id,
):
    conta = buscar_conta_codigo(conta_id)

    if not conta:
        await query.answer(
            "❌ Conta não encontrada.",
            show_alert=True,
        )
        return

    (
        _,
        servico,
        apelido,
        provedor,
        email_conta,
        senha_app,
        remetentes,
        ativa,
    ) = conta

    if not ativa:
        await query.answer(
            "❌ Essa conta está desativada.",
            show_alert=True,
        )
        return

    cliente = query.from_user

    if provedor in PROVEDORES_AUTOMATICOS:

        await query.edit_message_text(
            f"⏳ *Buscando código de {apelido}...*\n\n"
            "Isso pode levar alguns segundos.",
            parse_mode="Markdown",
        )

        resultado = buscar_codigo_imap(
            provedor,
            email_conta,
            senha_app,
            remetentes,
        )

        if resultado.get("erro"):
            await query.edit_message_text(
                f"❌ {resultado['erro']}",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔄 Tentar de novo",
                                callback_data=(
                                    f"buscarconta_{conta_id}"
                                ),
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🏠 Menu",
                                callback_data="menu",
                            )
                        ],
                    ]
                ),
            )
            return

        texto = (
            f"✅ *CÓDIGO ENCONTRADO — {apelido}*\n\n"
        )

        if resultado.get("codigo"):
            texto += (
                f"🔢 *Código:* `{resultado['codigo']}`\n\n"
            )

        if resultado.get("link"):
            texto += (
                f"🔗 *Link:* {resultado['link']}\n\n"
            )

        if resultado.get("assunto"):
            texto += (
                f"📧 *Assunto:* {resultado['assunto']}\n\n"
            )

        texto += (
            f"📝 *Trecho do email:*\n"
            f"_{resultado.get('resumo', '')}_"
        )

        await query.edit_message_text(
            texto,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔄 Buscar de novo",
                            callback_data=(
                                f"buscarconta_{conta_id}"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🏠 Menu",
                            callback_data="menu",
                        )
                    ],
                ]
            ),
            parse_mode="Markdown",
        )
        return

    if provedor in PROVEDORES_MANUAIS:

        pedido_id = criar_pedido_codigo(
            conta_id,
            cliente.id,
        )

        nome_cliente = (
            cliente.first_name or "cliente"
        )
        username_cliente = (
            f"@{cliente.username}"
            if cliente.username
            else "Não informado"
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 *PEDIDO DE CÓDIGO (MANUAL)*\n\n"
                    f"📦 Conta: {apelido} ({servico})\n"
                    f"👤 Cliente: {nome_cliente}\n"
                    f"🔗 Username: {username_cliente}\n"
                    f"🆔 ID do pedido: `{pedido_id}`\n"
                    f"🆔 ID do cliente: `{cliente.id}`\n\n"
                    "↩️ Responda esta mensagem com o "
                    "código pra encaminhar ao cliente."
                ),
                parse_mode="Markdown",
            )
        except Exception as erro:
            print(
                "ERRO AO NOTIFICAR ADMIN "
                "(pedido manual):",
                repr(erro),
            )

        await query.edit_message_text(
            f"⏳ *Pedido enviado — {apelido}*\n\n"
            "Aguarde, alguém vai te mandar o "
            "código por aqui em instantes.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🏠 Menu",
                            callback_data="menu",
                        )
                    ]
                ]
            ),
            parse_mode="Markdown",
        )
        return

    await query.answer(
        "❌ Provedor não configurado "
        "corretamente.",
        show_alert=True,
    )


# =========================================================
# ADMIN: RESPONDER PEDIDO MANUAL (PROTON)
# =========================================================

async def responder_pedido_manual(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    usuario = update.effective_user

    if not usuario or not is_admin(usuario.id):
        return

    mensagem = update.message

    if not mensagem or not mensagem.reply_to_message:
        return

    texto_original = (
        mensagem.reply_to_message.text or ""
    )

    match_pedido = re.search(
        r"ID do pedido:\s*`?(\d+)`?",
        texto_original,
    )
    match_cliente = re.search(
        r"ID do cliente:\s*`?(\d+)`?",
        texto_original,
    )

    if not match_pedido or not match_cliente:
        return

    pedido_id = int(match_pedido.group(1))
    cliente_id = int(match_cliente.group(1))

    if not mensagem.text:
        return

    try:
        await context.bot.send_message(
            chat_id=cliente_id,
            text=(
                "✅ *CÓDIGO RECEBIDO!*\n\n"
                f"{mensagem.text}"
            ),
            parse_mode="Markdown",
        )

        marcar_pedido_atendido(pedido_id)

        await mensagem.reply_text(
            "✅ Código enviado ao cliente."
        )

    except Exception as erro:
        print(
            "ERRO AO ENVIAR CÓDIGO MANUAL:",
            repr(erro),
        )

        await mensagem.reply_text(
            "❌ Não consegui enviar ao cliente "
            "(ele pode ter bloqueado o bot)."
        )


# =========================================================
# ADMIN: CADASTRAR NOVA CONTA (FLUXO SEQUENCIAL)
# =========================================================

async def iniciar_nova_conta(
    query,
    context,
):
    context.user_data.clear()
    context.user_data["cadastro_dados"] = {}
    context.user_data["cadastro_passo"] = 0

    _, pergunta = CAMPOS_CADASTRO[0]

    await query.edit_message_text(
        f"➕ *NOVA CONTA*\n\n{pergunta}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data="admmenu",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )


async def processar_passo_cadastro(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if "cadastro_passo" not in context.user_data:
        return False

    if not update.message or not update.message.text:
        return True

    passo = context.user_data["cadastro_passo"]
    campo, _ = CAMPOS_CADASTRO[passo]

    texto = update.message.text.strip()

    if campo == "provedor":
        texto_normalizado = texto.lower()
        if texto_normalizado not in (
            "gmail",
            "outlook",
            "proton",
        ):
            await update.message.reply_text(
                "❌ Digite exatamente: `gmail`, "
                "`outlook` ou `proton`.",
                parse_mode="Markdown",
            )
            return True
        valor = texto_normalizado

    elif texto.lower() == "pular":
        valor = None

    else:
        valor = texto

    context.user_data["cadastro_dados"][campo] = valor

    proximo_passo = passo + 1

    if proximo_passo < len(CAMPOS_CADASTRO):

        context.user_data["cadastro_passo"] = (
            proximo_passo
        )

        _, pergunta = CAMPOS_CADASTRO[proximo_passo]

        await update.message.reply_text(
            pergunta,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "❌ Cancelar",
                            callback_data="admmenu",
                        )
                    ]
                ]
            ),
            parse_mode="Markdown",
        )
        return True

    dados = context.user_data["cadastro_dados"]

    conta_id = cadastrar_conta_codigo(
        servico=dados.get("servico") or "Sem nome",
        apelido=dados.get("apelido") or "Sem apelido",
        provedor=dados.get("provedor") or "gmail",
        email=dados.get("email") or "",
        senha_app=dados.get("senha_app"),
        remetentes=dados.get("remetentes"),
    )

    context.user_data.clear()

    await update.message.reply_text(
        "✅ *CONTA CADASTRADA!*\n\n"
        f"🆔 ID: `{conta_id}`\n"
        f"📺 {dados.get('servico')} — "
        f"{dados.get('apelido')}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👑 Painel admin",
                        callback_data="admmenu",
                    )
                ]
            ]
        ),
        parse_mode="Markdown",
    )
    return True


# =========================================================
# ADMIN: LISTAR / GERENCIAR CONTAS
# =========================================================

async def mostrar_lista_admin(
    query,
):
    contas = listar_todas_contas_codigo()

    if not contas:
        await query.edit_message_text(
            "📋 Nenhuma conta cadastrada ainda.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Nova conta",
                            callback_data="admnova",
                        )
                    ]
                ]
            ),
        )
        return

    botoes = []

    for conta_id, servico, apelido, provedor, ativa in contas:

        emoji = "✅" if ativa else "⚫"

        botoes.append(
            [
                InlineKeyboardButton(
                    f"{emoji} {servico} — {apelido} "
                    f"({provedor})",
                    callback_data=(
                        f"admconta_{conta_id}"
                    ),
                )
            ]
        )

    botoes.append(
        [
            InlineKeyboardButton(
                "🏠 Menu admin",
                callback_data="admmenu",
            )
        ]
    )

    await query.edit_message_text(
        "📋 *CONTAS CADASTRADAS*\n\n"
        "Toque numa conta pra gerenciar:",
        reply_markup=InlineKeyboardMarkup(
            botoes
        ),
        parse_mode="Markdown",
    )


async def mostrar_detalhes_admin(
    query,
    conta_id,
):
    conta = buscar_conta_codigo(conta_id)

    if not conta:
        await query.answer(
            "❌ Conta não encontrada.",
            show_alert=True,
        )
        return

    (
        _,
        servico,
        apelido,
        provedor,
        email_conta,
        senha_app,
        remetentes,
        ativa,
    ) = conta

    texto = (
        f"📦 *{servico} — {apelido}*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📧 Provedor: {provedor}\n"
        f"✉️ Email: {email_conta}\n"
        f"🔑 Senha de app: "
        f"{'••••••' if senha_app else '—'}\n"
        f"📨 Remetentes: {remetentes or '(qualquer um)'}\n"
        f"📊 Status: "
        f"{'✅ Ativa' if ativa else '⚫ Inativa'}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        (
                            "⚫ Desativar"
                            if ativa
                            else "✅ Ativar"
                        ),
                        callback_data=(
                            f"admtoggle_{conta_id}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗑️ Excluir",
                        callback_data=(
                            f"admexcluir_{conta_id}"
                        ),
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Voltar",
                        callback_data="admlistar",
                    )
                ],
            ]
        ),
        parse_mode="Markdown",
    )


# =========================================================
# BOTÕES (ROTEADOR)
# =========================================================

async def botoes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    acao = query.data or ""

    if acao == "menu":
        context.user_data.clear()

        await query.edit_message_text(
            "🔑 *BOT DE CÓDIGOS*\n\n"
            "Escolha o serviço que você "
            "precisa do código de acesso:",
            reply_markup=menu_principal(),
            parse_mode="Markdown",
        )
        return

    if acao == "pegar_codigo":
        await mostrar_lista_servicos(query)
        return

    if acao.startswith("servico_"):
        try:
            indice = int(
                acao.replace("servico_", "", 1)
            )
        except ValueError:
            await query.answer(
                "❌ Serviço inválido.",
                show_alert=True,
            )
            return

        await mostrar_contas_do_servico(
            query,
            context,
            indice,
        )
        return

    if acao.startswith("buscarconta_"):
        try:
            conta_id = int(
                acao.replace(
                    "buscarconta_", "", 1
                )
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        await processar_pedido_codigo(
            query,
            context,
            conta_id,
        )
        return

    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    if not is_admin(query.from_user.id):
        await query.answer(
            "❌ Acesso negado.",
            show_alert=True,
        )
        return

    if acao == "admmenu":
        context.user_data.clear()

        await query.edit_message_text(
            "👑 *PAINEL ADMIN*\n\n"
            "Gerencie as contas de código:",
            reply_markup=menu_admin(),
            parse_mode="Markdown",
        )
        return

    if acao == "admnova":
        await iniciar_nova_conta(
            query,
            context,
        )
        return

    if acao == "admlistar":
        await mostrar_lista_admin(query)
        return

    if acao.startswith("admconta_"):
        try:
            conta_id = int(
                acao.replace("admconta_", "", 1)
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        await mostrar_detalhes_admin(
            query,
            conta_id,
        )
        return

    if acao.startswith("admtoggle_"):
        try:
            conta_id = int(
                acao.replace("admtoggle_", "", 1)
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        conta = buscar_conta_codigo(conta_id)

        if not conta:
            await query.answer(
                "❌ Conta não encontrada.",
                show_alert=True,
            )
            return

        ativa_atual = conta[7]

        definir_ativa_conta_codigo(
            conta_id,
            not ativa_atual,
        )

        await mostrar_detalhes_admin(
            query,
            conta_id,
        )
        return

    if acao.startswith("admexcluir_"):
        try:
            conta_id = int(
                acao.replace(
                    "admexcluir_", "", 1
                )
            )
        except ValueError:
            await query.answer(
                "❌ Conta inválida.",
                show_alert=True,
            )
            return

        excluir_conta_codigo(conta_id)

        await query.edit_message_text(
            "✅ Conta excluída.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🏠 Menu admin",
                            callback_data="admmenu",
                        )
                    ]
                ]
            ),
        )
        return

    await query.answer(
        "❌ Opção não reconhecida.",
        show_alert=True,
    )


# =========================================================
# PROCESSAR TEXTO
# =========================================================

async def processar_mensagem_texto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    usuario = update.effective_user

    if not usuario or not is_admin(usuario.id):
        return

    await processar_passo_cadastro(
        update,
        context,
    )


# =========================================================
# ERRO GLOBAL
# =========================================================

async def erro_global(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    print("❌ ERRO GLOBAL:")
    print(repr(context.error))


# =========================================================
# MAIN
# =========================================================

# =========================================================
# REGISTRAR MENU DE COMANDOS DO TELEGRAM
# =========================================================

async def configurar_comandos(
    application: Application,
):
    try:
        await application.bot.set_my_commands(
            [
                BotCommand(
                    "start",
                    "Pegar código de acesso",
                ),
                BotCommand(
                    "admin",
                    "Painel administrativo",
                ),
            ]
        )
    except Exception as erro:
        print(
            "ERRO AO REGISTRAR COMANDOS:",
            repr(erro),
        )


# =========================================================
# MAIN
# =========================================================

def main():
    verificar_configuracao()
    criar_tabelas()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(configurar_comandos)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("admin", comando_admin)
    )

    application.add_handler(
        CallbackQueryHandler(botoes)
    )

    application.add_handler(
        MessageHandler(
            filters.REPLY
            & filters.TEXT,
            responder_pedido_manual,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            processar_mensagem_texto,
        )
    )

    application.add_error_handler(
        erro_global
    )

    print("🔑 Bot de Códigos iniciado!")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
