# adStudioAI

SaaS multi-tenant de gestão de WhatsApp Business + Instagram + Meta Ads com autenticação JWT, WebSocket em tempo real e integração completa com a Meta Cloud API.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11 + FastAPI (async) |
| Banco | PostgreSQL 17 + SQLAlchemy 2.0 async + asyncpg |
| Frontend | React 19 + TypeScript + Vite + Tailwind CSS |
| Auth | JWT (python-jose) + bcrypt |
| WebSocket | FastAPI WebSocket nativo |
| Containers | Docker + Docker Compose |
| Criptografia | Fernet (cryptography) para tokens em repouso |
| Testes | pytest + pytest-asyncio + SQLite in-memory |
| Túnel local | ngrok (testes com webhook Meta) |

---

## Como rodar localmente

### Pré-requisitos

- Docker + Docker Compose instalados
- Python 3.11+ (só para gerar o `FERNET_KEY`)
- ngrok instalado ([ngrok.com/download](https://ngrok.com/download))

---

### 1. Clone e configure o `.env`

```bash
cp backend/.env.example backend/.env
```

Edite `backend/.env` com os valores abaixo:

```env
# PostgreSQL (não mude — já está configurado no docker-compose)
DATABASE_URL=postgresql+asyncpg://marketing_user:marketing_pass@localhost:5432/adstudioai

# Meta / Facebook Graph API
META_APP_ID=seu_app_id
META_APP_SECRET=seu_app_secret
META_API_VERSION=v21.0
META_REDIRECT_URI=https://ngoc-subumbellate-jayce.ngrok-free.dev/api/v1/auth/meta/callback
META_WEBHOOK_VERIFY_TOKEN=adstudioai_webhook_2024

# Criptografia de tokens (obrigatório — gere uma chave única)
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FERNET_KEY=sua_chave_fernet_aqui

# JWT
SECRET_KEY=uma_string_aleatoria_longa_e_segura

# CORS
CORS_ORIGINS=["http://localhost:5173","https://ngoc-subumbellate-jayce.ngrok-free.dev"]

# ngrok (túnel para testes com Meta webhook)
NGROK_AUTHTOKEN=34UhOfU7kacd1lnqQrSEoHEic7H_7NgzRUeGJp97zi9KbSBet
NGROK_DOMAIN=ngoc-subumbellate-jayce.ngrok-free.dev

# n8n (opcional — se vazio, eventos são apenas logados)
N8N_WEBHOOK_URL=
```

---

### 2. Suba os containers

```bash
docker compose up --build -d
```

Aguarda subir tudo (~30s na primeira vez). Verifique:

```bash
docker compose ps
```

Todos devem estar `healthy` ou `Up`.

---

### 3. Abra o ngrok (terminal separado — deixe aberto)

```bash
# Adicione o authtoken uma única vez
ngrok config add-authtoken 34UhOfU7kacd1lnqQrSEoHEic7H_7NgzRUeGJp97zi9KbSBet

# Sobe o túnel
ngrok http --url=ngoc-subumbellate-jayce.ngrok-free.dev 8000
```

---

### 4. Acesse

| Serviço | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| API pública (ngrok) | https://ngoc-subumbellate-jayce.ngrok-free.dev |

---

### 5. Configure o webhook no Meta for Developers

1. Acesse [developers.facebook.com](https://developers.facebook.com) → seu App → WhatsApp → Configuração
2. **Webhook URL:** `https://ngoc-subumbellate-jayce.ngrok-free.dev/api/v1/webhook/meta`
3. **Verify Token:** `adstudioai_webhook_2024`
4. Clique em **Verificar e salvar**
5. Assine o campo **messages**

---

## Primeiro uso — criar conta e testar

```bash
# 1. Registrar tenant + usuário admin
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"brand_name":"Minha Empresa","username":"admin","password":"senha123"}'

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"senha123"}'
# → retorna access_token e refresh_token

# 3. Configurar credenciais WhatsApp
curl -X PUT http://localhost:8000/api/v1/whatsapp/credentials \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number_id": "SEU_PHONE_NUMBER_ID",
    "phone_number": "+55 83 99999-9999",
    "waba_id": "SEU_WABA_ID",
    "access_token": "SEU_SYSTEM_USER_TOKEN"
  }'
```

---

## API — Endpoints

### Auth JWT

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/auth/register` | Cria tenant + usuário admin. Retorna tokens |
| POST | `/api/v1/auth/login` | `{username, password}` → `{access_token, refresh_token}` |
| POST | `/api/v1/auth/refresh` | Renova access_token com refresh_token |
| GET | `/api/v1/auth/me` | Retorna usuário autenticado |
| POST | `/api/v1/auth/users` | Admin cria agente no tenant |
| GET | `/api/v1/auth/users` | Lista usuários do tenant |

Todas as rotas protegidas exigem `Authorization: Bearer <access_token>`.

---

### Pagamentos (Asaas)

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| GET | `/api/v1/payments/plans` | Pública | Lista planos disponíveis (Gratuito, Starter R$99, Pro R$299, Premium R$899) |
| POST | `/api/v1/payments/checkout` | Pública | Checkout sem login: cria conta temporária + cobrança no Asaas. Body: `{plan, name, email}`. Redireciona para `payment_link` |
| POST | `/api/v1/payments/subscribe` | JWT | Cria assinatura para usuário logado. Retorna `payment_link` |
| GET | `/api/v1/payments/current` | JWT | Retorna assinatura ativa do tenant |
| POST | `/api/v1/payments/upgrade` | JWT | Faz upgrade de plano (cancela atual + cria nova) |
| POST | `/api/v1/payments/webhook/asaas` | Pública | Webhook do Asaas (valida `asaas-access-token`). Confirma/cancela assinaturas |

### Auth — Pós-pagamento

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| POST | `/api/v1/auth/complete-signup` | Pública | Define senha após pagamento. Body: `{email, password}`. Retorna JWT |

---

### WhatsApp Business

| Método | Rota | Descrição |
|---|---|---|
| PUT | `/api/v1/whatsapp/credentials` | Admin configura phone_id, waba_id, token |
| GET | `/api/v1/whatsapp/credentials` | Consulta conexão atual |
| POST | `/api/v1/whatsapp/send` | Envia texto livre (janela de 24h) |
| POST | `/api/v1/whatsapp/send-template` | Envia template aprovado (fora da janela) |
| GET | `/api/v1/whatsapp/templates` | Lista templates do cache local |
| POST | `/api/v1/whatsapp/templates/sync` | Sincroniza templates da Meta API |
| POST | `/api/v1/whatsapp/templates` | Cria template para aprovação |
| DELETE | `/api/v1/whatsapp/templates/{name}` | Deleta template |
| GET | `/api/v1/whatsapp/stats` | Contadores mensais (marketing/utility/service/auth) |

---

### Conversas

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/conversations` | Lista conversas do tenant (filtra por status, atendente) |
| POST | `/api/v1/conversations` | Cria conversa |
| GET | `/api/v1/conversations/{id}` | Detalhe |
| PATCH | `/api/v1/conversations/{id}` | Atualiza status, atendente, unread_count |
| DELETE | `/api/v1/conversations/{id}` | Remove |

---

### Mensagens

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/conversations/{id}/messages` | Lista mensagens (paginado, ordem cronológica) |
| POST | `/api/v1/conversations/{id}/messages` | Salva mensagem (uso interno / testes) |
| PATCH | `/api/v1/conversations/{id}/messages/{msg_id}/status` | Atualiza status (delivered/read/failed) |

---

### WebSocket — tempo real

```
ws://localhost:8000/ws?token=<access_token>
```

**Eventos recebidos pelo frontend:**

| Evento | Quando dispara |
|---|---|
| `new_message` | Nova mensagem inbound (webhook) ou outbound (agente) |
| `message_status_updated` | Atualização de status (delivered, read, failed) |
| `conversation_created` | Nova conversa criada |
| `conversation_updated` | unread_count, status ou atendente atualizados |

Cada tenant recebe apenas seus próprios eventos. Keepalive: envie `ping` → responde `pong`.

---

### Webhook Meta

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/webhook/meta` | Verificação de challenge (Meta valida o endpoint) |
| POST | `/api/v1/webhook/meta` | Recebe eventos (valida `X-Hub-Signature-256` antes de qualquer processamento) |

**Roteamento automático:**
- `object=whatsapp_business_account` → roteia por `phone_number_id` → cria Lead + Conversa + Message + broadcast WS
- `object=instagram` → roteia por `page_id` → captura lead + auto-reply por keyword

---

### Automações (comentário → DM / WhatsApp)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/automations` | Cria automação (keyword, canal, post opcional, mensagens) |
| GET | `/api/v1/automations` | Lista automações do tenant |
| GET | `/api/v1/automations/{id}` | Detalhe |
| PUT | `/api/v1/automations/{id}` | Atualiza (parcial) |
| DELETE | `/api/v1/automations/{id}` | Remove |

Cada `AutomationConfig` reage a uma `keyword` em um ou dois canais (`trigger_type`: `comment` · `dm` · `both`), opcionalmente restrita a um post/reel específico (`media_id`). Quando um comentário do Instagram bate com a keyword:

1. Responde publicamente no comentário com `comment_reply_message` (ou `auto_reply_message` como fallback), via `POST /{comment_id}/replies`.
2. Se `dm_message` estiver preenchido, envia uma DM privada para quem comentou via `POST /me/messages` com `recipient.comment_id` ("private reply") — sem precisar de conversa prévia.

Restrições da Meta (não configuráveis): a DM privada só pode ser enviada até 7 dias após o comentário, e apenas uma vez por comentário.

---

### Meta OAuth (Instagram / Ads)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/auth/meta/start?provider=` | Gera URL OAuth com state HMAC assinado |
| GET | `/api/v1/auth/meta/callback` | Troca code → long-lived token, persiste MetaConnection |
| GET | `/api/v1/auth/meta/connections` | Lista conexões ativas do tenant |
| DELETE | `/api/v1/auth/meta/connections/{id}` | Revoga e remove conexão |

**Providers:** `instagram` · `whatsapp` · `ads`

---

### Nota para Claude: Login Meta, Instagram Login e WhatsApp Embedded Signup

Existem tres fluxos diferentes e eles nao devem ser misturados:

1. **Facebook Login for Business / Meta OAuth**
   - Usa `https://www.facebook.com/{version}/dialog/oauth`.
   - No projeto fica em `/api/v1/auth/meta/start` e `/api/v1/auth/meta/callback`.
   - Serve para conectar permissoes e ativos Meta existentes via Facebook/Business Manager, como paginas, conta de anuncios e permissoes classicas.
   - Scopes tipicos: `pages_show_list`, `pages_read_engagement`, `instagram_manage_comments`, `ads_management`, `business_management`, `whatsapp_business_management`.
   - Nao usar scopes `instagram_business_*` nesse fluxo, porque eles pertencem ao Instagram Login.

2. **Instagram Business Login**
   - Usa `https://www.instagram.com/oauth/authorize`.
   - No projeto fica em `/api/v1/auth/instagram/start` e `/api/v1/auth/instagram/callback`.
   - Serve para conectar diretamente uma conta profissional do Instagram.
   - Scopes usados pelo projeto: `instagram_business_basic`, `instagram_business_manage_messages`, `instagram_business_manage_comments`, `instagram_business_content_publish`, `instagram_business_manage_insights`.
   - A URL deve ser gerada pelo endpoint `/api/v1/auth/instagram/start?account_id=<tenant_id>`, porque o backend exige `state` assinado no callback.
   - Redirect local/ngrok atual usado nos testes: `https://greedily-trunks-morally.ngrok-free.dev/api/v1/auth/instagram/callback`.

3. **WhatsApp Embedded Signup**
   - Nao e apenas OAuth com redirect.
   - E o onboarding incorporado para criar/conectar WABA, numero de telefone e permissoes de WhatsApp do cliente.
   - Deve usar Facebook JS SDK com `WHATSAPP_CONFIG_ID`/`config_id` e retorno via evento/postMessage.
   - E o caminho correto para producao multi-cliente de WhatsApp.

URLs configuradas no painel Meta para o Instagram Business Login:

| Campo Meta | URL |
|---|---|
| OAuth redirect URI | `https://greedily-trunks-morally.ngrok-free.dev/api/v1/auth/instagram/callback` |
| Deauthorize callback URL | `https://greedily-trunks-morally.ngrok-free.dev/api/v1/privacy/deauthorize` |
| Data deletion request URL | `https://greedily-trunks-morally.ngrok-free.dev/api/v1/privacy/data-deletion` |

---

## Banco de Dados

### Tabelas e relações

```
accounts (tenant)
  ├── users           (agentes do tenant — FK tenant_id)
  ├── meta_connections (conexões Meta por provider — FK account_id)
  ├── leads           (contatos capturados — FK account_id)
  │   └── conversations (atendimentos — FK tenant_id + customer_id)
  │       └── messages  (histórico — FK tenant_id + conversation_id)
  ├── automation_configs
  └── video_generations
```

### `users`

| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | FK → accounts, CASCADE |
| username | String(100) | UNIQUE global |
| password_hash | Text | bcrypt |
| full_name | String | opcional |
| role | String | `admin` · `agent` |
| is_active | Boolean | |

### `conversations`

| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | FK → accounts |
| customer_id | UUID | FK → leads (SET NULL) |
| atendente_id | UUID | FK → users (SET NULL) |
| atendimento_status | String | `aberto` · `em_atendimento` · `resolvido` · `aguardando` |
| status | String | `active` · `closed` |
| unread_count | Integer | Incrementado pelo webhook |
| last_updated | DateTime | Atualizado a cada mensagem |

### `messages`

| Campo | Tipo | Notas |
|---|---|---|
| id | BigSerial | PK |
| tenant_id | UUID | FK → accounts |
| conversation_id | UUID | FK → conversations, CASCADE |
| sender | Text | username do agente ou wa_id do cliente |
| text | Text | corpo da mensagem |
| direction | String | `inbound` · `outbound` |
| wa_id | Text | número WhatsApp do cliente |
| status | String | `sent` · `delivered` · `read` · `failed` |
| message_id | Text | wamid da Meta (indexado) |
| media_type | Text | `image` · `video` · `audio` · `document` |
| media_url | String | URL pública da mídia |
| meta_category | String(50) | `marketing` · `utility` · `service` · `authentication` |
| meta_cost | Float | custo da conversa em USD |
| is_within_24h_window | Boolean | janela de 24h do WhatsApp |
| template_name | Text | nome do template (se aplicável) |
| template_vars | JSON | variáveis `{{1}}`, `{{2}}`... |
| payload | JSON | raw payload da Meta |

### `meta_connections`

| Campo | Tipo | Notas |
|---|---|---|
| account_id | UUID | FK → accounts |
| provider | String | `instagram` · `whatsapp` · `ads` |
| phone_number_id | String | ID do número Meta — chave de roteamento do webhook |
| phone_number | String | número exibível (`+55 83 ...`) |
| waba_id | String | WhatsApp Business Account ID |
| access_token_encrypted | Text | Fernet encrypted |
| meta_templates | JSON | templates sincronizados da Meta |
| conv_count_marketing | Integer | contador mensal |
| conv_count_utility | Integer | contador mensal |
| conv_count_service | Integer | contador mensal |
| conv_count_auth | Integer | contador mensal |

---

## Testes

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

Usa SQLite in-memory — sem necessidade de PostgreSQL ou Docker.

| Arquivo | Cobertura |
|---|---|
| `test_webhook.py` | HMAC, challenge, lead creation, auto-reply, no-duplicate |
| `test_auth.py` | State HMAC, token encrypt/decrypt, connections endpoints |
| `test_tenant.py` | Isolamento por tenant, DELETE cross-tenant bloqueado |

---

## Estrutura de arquivos

```
app-marketing/
├── docker-compose.yml
├── backend/
│   ├── .env                      # NÃO commitar
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── tests/
│   └── app/
│       ├── main.py               # FastAPI app, lifespan (create_all + migrations)
│       ├── core/
│       │   ├── config.py         # Pydantic Settings
│       │   ├── database.py       # Async engine + get_db
│       │   ├── security.py       # JWT + bcrypt
│       │   └── ws_manager.py     # WebSocket ConnectionManager (singleton)
│       ├── models/
│       │   ├── account.py        # Tenant
│       │   ├── user.py           # Usuários + autenticação
│       │   ├── conversation.py   # Atendimentos
│       │   ├── message.py        # Histórico de mensagens
│       │   ├── meta_connection.py # Conexões Meta por provider
│       │   └── lead.py           # Leads/contatos
│       ├── routes/
│       │   ├── auth_jwt.py       # Register, login, refresh, me, users
│       │   ├── conversations.py  # CRUD conversas
│       │   ├── messages.py       # CRUD mensagens
│       │   ├── ws.py             # WebSocket endpoint
│       │   ├── whatsapp.py       # Credenciais, envio, templates
│       │   ├── webhook.py        # Meta webhook (IG + WhatsApp)
│       │   ├── auth.py           # OAuth Meta multi-provider
│       │   └── privacy.py        # Privacy policy + data deletion
│       └── services/
│           ├── whatsapp_service.py   # Cloud API: send, template, media
│           ├── instagram_service.py  # DM, comment, publish
│           ├── meta_token_service.py # Fernet, long-lived token, state HMAC
│           └── ads_service.py        # Campanhas e insights
└── frontend/
    └── src/
        ├── App.tsx
        └── pages/
            ├── ConexaoMeta.tsx   # Cards Instagram / WhatsApp / Ads
            ├── Dashboard.tsx
            ├── Leads.tsx
            ├── Automacao.tsx
            ├── Studio.tsx
            └── Privacy.tsx
```

---

## Deploy produção

Quando for para domínio público:

1. Atualize no `.env` de produção:
   ```env
   META_REDIRECT_URI=https://seudominio.com/api/v1/auth/meta/callback
   CORS_ORIGINS=["https://seudominio.com"]
   FERNET_KEY=nova_chave_diferente_do_local
   SECRET_KEY=chave_jwt_longa_e_aleatoria
   ```

2. Configure webhook no Meta Dashboard com a URL de produção
3. Submeta o app para App Review com as permissões `whatsapp_business_messaging` e `whatsapp_business_management`
-"já feito isso do wpp"-Dev
