# Prospecta

SaaS multi-tenant da Destrava para atendimento e vendas pela Meta: inbox de WhatsApp e Instagram Direct, leads, automações, assistente de IA e campanhas de anúncios.

- **Site:** https://prospecta.sistemasdestrava.com.br
- **API:** https://api.prospecta.sistemasdestrava.com.br (documentação interativa em `/docs`)
- **Manual de uso:** o Guia do sistema, no painel em `/app/guia` e público em `/guia`

Este README é para quem desenvolve o projeto.

## Stack

| Camada | Tecnologia |
|---|---|
| API | Python 3.11, FastAPI (async), SQLAlchemy 2.0, asyncpg |
| Banco | PostgreSQL; SQLite em memória nos testes |
| Cache e coordenação | Redis, com fallback em memória quando `REDIS_URL` está vazio |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Tempo real | WebSocket em `/ws` |
| Autenticação | JWT (python-jose) e bcrypt |
| Criptografia | Fernet para tokens da Meta e chaves de API em repouso |
| IA | Gemini com RAG, usando a chave de API de cada cliente |
| Deploy | Render (Blueprint em `render.yaml`) |

## Estrutura

```text
backend/app/
  core/       configuração, banco, Redis, segurança, módulos, WebSocket, i18n
  models/     tabelas (SQLAlchemy)
  routes/     endpoints: webhook, whatsapp, whatsapp_calls, conversations, leads,
              instagram, marketing, ai, auth, clients, payments, privacy, ws...
  services/   Meta (whatsapp, instagram, ads), IA, RAG, follow-up, agendador, chamadas
backend/tests/   pytest
frontend/src/
  pages/      uma tela por arquivo
  components/ Layout, Sidebar, CallProvider e painéis
  i18n/       t('português', 'english') em componentes; tr() fora deles
docs/         roteiro e guia de submissão do App Review da Meta
infra/        manifestos Kubernetes e Terraform (a produção atual usa o Render)
```

## Rodar localmente

Com Docker:

```bash
cp backend/.env.example backend/.env   # preencha FERNET_KEY, SECRET_KEY e as chaves da Meta
docker compose up --build -d
```

| Serviço | Endereço |
|---|---|
| Frontend | http://localhost:5173 |
| API e documentação | http://localhost:8001/docs |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6380 |

Gere a `FERNET_KEY` com:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

O `docker-compose.yml` sobe a API com 4 workers por padrão. Como o agendador roda dentro do processo da API, use `UVICORN_WORKERS=1` se for testar posts agendados ou follow-ups, para não enviar em duplicidade.

Para receber webhooks da Meta na sua máquina, exponha a API por um túnel e defina `PUBLIC_BASE_URL` com a URL pública.

## Testes

```bash
cd backend && pytest                 # usa SQLite em memória, sem Docker nem Postgres
cd frontend && npm run build         # checa os tipos e compila
```

O CI está em `.github/workflows/ci.yml`. O SQLite não reproduz tudo do Postgres, como enums nativos e `ALTER TYPE`: ao mudar o schema, teste também num Postgres real.

## Banco de dados e migrações

Na inicialização, a API roda `Base.metadata.create_all` e depois a lista `_MIGRATIONS` de `backend/app/main.py`, com SQL idempotente. É esse caminho que vale em produção. O Alembic existe no repositório, mas não roda no deploy.

- **Tabela nova:** basta importar o modelo em `main.py`.
- **Coluna nova:** adicione um `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` em `_MIGRATIONS`.
- **Valor novo em enum (como `lead_source`):** adicione um `ALTER TYPE ... ADD VALUE IF NOT EXISTS`, porque `create_all` não altera um tipo que já existe.

## Variáveis de ambiente

A lista completa está em `backend/.env.example`. As principais:

| Variável | Para quê |
|---|---|
| `DATABASE_URL`, `REDIS_URL` | Banco e Redis |
| `SECRET_KEY`, `FERNET_KEY` | Assinatura do JWT e criptografia em repouso |
| `META_APP_ID`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN` | App da Meta e validação de webhooks |
| `META_API_VERSION` | Versão da Graph API (hoje `v21.0`, que expira em 21/01/2027) |
| `WHATSAPP_CONFIG_ID` | Configuração do Cadastro Incorporado |
| `IG_APP_ID`, `IG_APP_SECRET` | Login do Instagram |
| `APP_URL`, `PUBLIC_BASE_URL`, `CORS_ORIGINS` | Endereços públicos |
| `SUPER_ADMIN_EMAILS` | Quem pode bloquear módulos de qualquer conta |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Armazenamento de mídia dos posts |
| `ASAAS_API_KEY`, `ASAAS_WEBHOOK_TOKEN` | Pagamentos |
| `RESEND_API_KEY` | E-mails |

Recursos ligados por variável, todos desligados por padrão:

| Variável | Efeito |
|---|---|
| `ADS_SYNC_ENABLED` | Sincroniza a Marketing API a cada 10 minutos |
| `WHATSAPP_CALLING_ENABLED` | Libera as chamadas de voz recebidas no WhatsApp |
| `WEBRTC_ICE_SERVERS` | Servidores STUN/TURN do navegador, em JSON (opcional) |
| `WS_REDIS_FANOUT` | Entrega eventos do WebSocket entre instâncias da API pelo Redis |

## Integração com a Meta

Todos os webhooks chegam em `POST /api/v1/webhook/meta`, com a assinatura validada por HMAC. O cliente é identificado pelo `phone_number_id` (WhatsApp) ou pelo ID da Página ou do Instagram.

| Tópico | Campos assinados |
|---|---|
| `whatsapp_business_account` | `messages`, `message_template_status_update`, `message_template_quality_update`, `calls` |
| `instagram` | `messages`, `comments` |
| `page` | `leadgen`, `leadgen_update` |

Cada cliente conecta a própria conta. Os tokens ficam criptografados em `meta_connections`.

## Isolamento entre clientes

Toda consulta filtra por `tenant_id` ou `account_id`, e o tenant vem sempre do JWT ou do webhook, nunca do corpo da requisição. Os módulos (`whatsapp`, `instagram`, `ads`, `ia`) são verificados por `require_module`.

O arquivo `backend/app/core/rls_policies.py` não está em uso: hoje o isolamento depende desses filtros no código, sem Row-Level Security ativo no banco.

## Chamadas de voz

O áudio vai direto do navegador do atendente para a Meta por WebRTC, e a API só faz a sinalização. Nada de áudio passa pelo servidor nem é gravado.

1. O webhook `calls` cria a chamada em `whatsapp_calls` e avisa quem tem o módulo WhatsApp.
2. Quem clica em Atender chama `claim`, um `UPDATE` condicional em que o primeiro vence.
3. O navegador envia a resposta SDP por `pre-accept` e `accept`, e só abre o microfone depois do `accept`.

Regras do código:

- O SDP fica criptografado só enquanto a chamada toca e nunca vai para logs, eventos ou `Message.payload`.
- A Meta pode repetir eventos ou mandar `terminate` antes de `connect`, então cada evento é idempotente sobre `(tenant_id, wa_call_id)`.

Para ativar, ligue `WHATSAPP_CALLING_ENABLED` e assine o campo `calls` no app da Meta. A Meta só libera ligações em contas com limite de 2.000 destinatários por dia ou mais; números de teste públicos são isentos. As chamadas feitas pela empresa ainda não existem.

## Deploy

Push na `main` publica sozinho pelo Render:

| Serviço | Tipo |
|---|---|
| `prospecta-api` | Web service em Python |
| `prospecta-web` | Site estático |
| `prospecta-db` | PostgreSQL |
| `prospecta-redis` | Redis (Key Value) |

Variáveis marcadas com `sync: false` no `render.yaml` são definidas no painel do Render.

## Limites atuais para escalar

Hoje a API roda em **uma instância com um worker**. Para rodar mais de uma, ainda falta:

- **Agendador:** posts, follow-ups e sync rodam dentro do processo da API, sem trava. Duas instâncias enviariam em duplicidade.
- **Disparos:** `POST /whatsapp/broadcast` envia em loop dentro da requisição HTTP, sem fila.
- **Webhook:** processa tudo inline, avisa o navegador antes de gravar no banco e pode chamar a Meta e a Gemini no meio da transação.
- **RAG:** carrega os trechos do cliente e calcula a similaridade em Python, a cada pergunta.

## Mais documentação

- `docs/META_APP_REVIEW.md`: guia de submissão à Meta
- `docs/SCREENCASTS.md`: roteiro dos vídeos do App Review
- `AGENTS.md`: instruções para agentes de código
