# Bot de Códigos

Bot de Telegram separado que entrega pro cliente o código de
verificação (ou link de confirmação de aparelho) que serviços
de streaming mandam por email — sem o cliente precisar acessar
a caixa de entrada da conta.

## Como funciona

- **Gmail e Outlook**: busca automática. O bot conecta na caixa
  de entrada via IMAP (com uma "senha de app", não a senha
  normal), acha o email mais recente do serviço e manda o
  código/link pro cliente na hora.
- **Proton Mail**: manual. O Proton não permite esse tipo de
  acesso automático sem um programa pago rodando 24h (Proton
  Mail Bridge). Nesse caso, o pedido do cliente cai no seu chat
  administrativo, e você (ou quem estiver de olho na caixa)
  responde com **Reply** direto na mensagem, com o código —
  o bot repassa pro cliente automaticamente.

## Arquivos
- `config.py` — variáveis de ambiente
- `database.py` — banco SQLite
- `main.py` — bot em si (inclui a lógica de IMAP)
- `requirements.txt` / `Procfile` — deploy

## Como colocar no ar (Railway)

1. Crie um repositório novo no GitHub com esses arquivos
   (`config.py`, `database.py`, `main.py`, `requirements.txt`,
   `Procfile`) — todos soltos, sem pasta.
2. No Railway → **"New Project"** → **"Deploy from GitHub repo"**
   → selecione o repositório.
3. Em **Variables**, adicione:
   - `BOT_TOKEN` — token de um bot novo (crie com @BotFather)
   - `ADMIN_ID` — seu ID numérico do Telegram (fale com
     @userinfobot)
4. Deploy automático.

## Como gerar a "senha de app" (Gmail e Outlook)

**Gmail:**
1. Ative a verificação em duas etapas na conta (obrigatório)
2. Acesse myaccount.google.com/apppasswords
3. Gere uma senha de app pra "Mail" — é essa senha (16
   caracteres, sem espaços) que vai no cadastro, **não** a
   senha normal da conta

**Outlook/Hotmail:**
1. Ative a verificação em duas etapas
2. Acesse account.microsoft.com/security → "Opções de
   segurança avançadas" → "Senha de app"
3. Gere e use essa senha no cadastro

## Como usar

**Cliente:**
- `/start` → **🔑 PEGAR CÓDIGO** → escolhe o serviço → (se
  tiver mais de uma conta pro mesmo serviço, escolhe qual) →
  recebe o código/link (automático) ou aguarda alguém te
  atender (manual, contas Proton)

**Admin (`/admin`):**
- **➕ NOVA CONTA** — cadastro passo a passo: serviço, apelido,
  provedor (`gmail`/`outlook`/`proton`), email, senha de app
  (pule se for Proton), remetentes que valem pra busca (opcional
  — se pular, pega qualquer email recente da caixa)
- **📋 LISTAR CONTAS** — vê todas, ativa/desativa ou exclui

## Observação sobre a extração do código

O bot tenta achar automaticamente um número de 4 a 8 dígitos e
qualquer link no corpo do email mais recente do remetente
configurado, e sempre mostra também um trecho do texto do email
— assim, mesmo se o padrão de um serviço específico mudar ou não
bater exatamente, o cliente ainda consegue ver o conteúdo
relevante. Se perceber que algum serviço específico está vindo
com informação a mais/a menos, me avise que ajusto a extração
pra esse caso.
