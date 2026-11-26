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
  i18n/       t('português', 'english') em componentes; tr() fora deles. Espanhol em i18n/es.ts, indexado pelo texto em português
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
| `SUPER_ADMIN_EMAILS` | Quem aprova cadastros e bloqueia módulos de qualquer conta |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Armazenamento de mídia dos posts |
| `ASAAS_API_KEY`, `ASAAS_WEBHOOK_TOKEN` | Pagamentos |
| `GEMINI_API_KEYS` | Chaves da Gemini da IA do Prospecta, separadas por vírgula |
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

## Aprovação de cadastro

Conta criada pelo cadastro ou pelo checkout nasce com `accounts.approval_status = 'pending'`. Ela não recebe token, e qualquer token antigo é recusado com 403 (`pending_approval` ou `account_rejected`) até o super admin aprovar em **Super Admin**. Os super admins recebem um e-mail a cada cadastro novo, e o cliente recebe outro quando é aprovado.

Contas que já existiam ficaram aprovadas. As empresas-filhas criadas por uma agência seguem a aprovação da conta-mãe.

## Planos e cobrança

Os planos ficam na tabela `plans` (criados na primeira subida com Essencial, Profissional e Agência) e são editados pelo super admin em **Super Admin → Planos**: preço, limites (`users`, `clients`, `ai_tokens`), módulos e itens extras.

Ao aprovar um cadastro, a conta ganha `BILLING_TRIAL_DAYS` (padrão 7) de teste no plano `BILLING_TRIAL_PLAN`. Em **Planos**, o cliente assina: o backend cria o cliente e uma assinatura mensal no Asaas (`billingType: UNDEFINED`, o cliente escolhe Pix, boleto ou cartão) e mostra o Pix da primeira cobrança. O webhook do Asaas (`/api/v1/payments/webhook/asaas`) libera até um mês depois do vencimento a cada pagamento; a tela também confere o pagamento direto no Asaas.

Quem tem acesso: cortesia do super admin (com ou sem prazo), pago até `paid_until` (mais `BILLING_GRACE_DAYS` de tolerância, padrão 3) ou teste em andamento. Contas com `billing_status` nulo ficam fora da cobrança; as que já existiam viraram cortesia sem prazo. Empresas-filhas seguem a agência.

Com `BILLING_ENFORCED=true`, quem não tem acesso recebe 402 (`billing_required`) em tudo menos `/billing`, `/auth`, `/admin` e `/payments`, e o painel leva para Planos; os limites de usuários, empresas clientes, módulos e tokens de IA passam a valer. Com `false` (padrão), os prazos e avisos aparecem, mas ninguém é bloqueado.

## IA do Prospecta

A conta escolhe em **IA e conhecimento** entre a IA do Prospecta (chaves de `GEMINI_API_KEYS`) e a própria chave da Gemini. Com a do Prospecta, o plano inclui `limits.ai_tokens` por mês, mostrados como atendimentos (`AI_TOKENS_PER_CONVERSATION`, padrão 20.000 tokens). A franquia soma a agência e as empresas-filhas e vale mesmo com `BILLING_ENFORCED=false`, porque a IA do Prospecta é paga por nós: no teste ela fica limitada a `AI_TRIAL_CONVERSATIONS` (padrão 100) e, com o teste ou o pagamento vencido, só sobram os pacotes extras. Contas sem plano ficam com `AI_DEFAULT_TOKEN_LIMIT`.

Modelo padrão: `gemini-3.5-flash-lite` (`GEMINI_MODEL`). Embeddings: `gemini-embedding-001` em 768 dimensões (`GEMINI_EMBEDDING_MODEL`, `GEMINI_EMBEDDING_DIMS`). Cada trecho guarda o modelo que o gerou, e trechos de outro modelo são refeitos automaticamente antes da próxima busca.

"Comprar mais" gera um Pix no Asaas de `AI_PACK_CONVERSATIONS` atendimentos por `AI_PACK_PRICE_CENTS`. O saldo (`accounts.ai_extra_tokens`) entra pelo webhook ou pela conferência da tela, é usado depois da franquia e não vence. Ao acabar tudo, as conversas vão para a fila humana.

Vazão: cada resposta pega uma vaga no Redis, limitada por conta (`AI_ACCOUNT_RPM`) e por chave (`AI_KEY_RPM`). A chave que recebe 429 fica `AI_KEY_COOLDOWN_SECONDS` em pausa e a próxima assume. Sem vaga em `AI_SLOT_WAIT_SECONDS`, a conversa vai para a fila humana. O super admin acompanha respostas, custo estimado, 429 e espera em **Super Admin → IA**.

## Posts do Instagram

O agendador reserva cada post vencido (`scheduled` → `publishing`) antes de publicar, então duas rodadas ou duas instâncias não publicam o mesmo post. Falha passageira volta para a fila com espera crescente (até 3 tentativas). Post parado em `publishing` por mais de 15 minutos, ou atrasado mais de 6 horas, vira `failed` sem ser publicado, e a tela pede para conferir no Instagram e usar "Tentar de novo".

Limites por empresa, definidos no plano (`scheduled_posts`, `storage_mb`, `automations`) ou, sem plano, por `DEFAULT_SCHEDULED_POSTS`, `DEFAULT_STORAGE_MB` e `DEFAULT_AUTOMATIONS`. Valem mesmo com `BILLING_ENFORCED=false`, porque são custo de armazenamento. Cada upload fica em `media_uploads` e conta na cota até ser apagado: ao publicar, ao remover o agendamento, quando sobra sem virar post (24h) e quando o post falhou e ficou parado (`FAILED_MEDIA_DAYS`, padrão 7). A automação de comentário de um post desliga sozinha depois de `POST_AUTOMATION_DAYS` (padrão 30) sem alteração.

## Disparos em massa

`POST /whatsapp/broadcast` só cria o disparo (`broadcast_jobs`) e a lista de destinatários (`broadcast_recipients`) e responde 202. O envio roda numa fila no Postgres, em lotes de 50 (`BROADCAST_SEND_CONCURRENCY` envios simultâneos), dentro do processo da API: começa logo depois da resposta e um loop a cada 2 segundos continua de onde parou, inclusive depois de reinício. Cada destinatário é reservado antes do envio (`SKIP LOCKED`), então duas instâncias não mandam duas vezes para o mesmo número. Quem ficou "enviando" por mais de 5 minutos (instância caiu) vira falha, sem reenvio.

As variáveis de cada contato (`{{primeiro_nome}}`, colunas do CSV) são resolvidas na hora do envio por `lead_vars.resolve`; campo vazio sem padrão, opt-out feito depois de criar o disparo e lead apagado viram `skipped`. Telefone repetido em dois leads recebe uma vez. Erro da conta ou do template antes do primeiro envio para o disparo inteiro. Um segundo disparo do mesmo template em andamento recebe 409 (`broadcast_running`). O progresso sai em `GET /whatsapp/broadcast/jobs/{id}` e `POST /whatsapp/broadcast/jobs/{id}/cancel` para o resto.

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

Para ativar, ligue `WHATSAPP_CALLING_ENABLED` e assine o campo `calls` no app da Meta. A Meta só libera ligações em contas com limite de 2.000 destinatários por dia ou mais; números de teste públicos são isentos. Ligar para o cliente (`POST /whatsapp/calls/outbound`) exige opt-in de WhatsApp no lead e a permissão do cliente na Meta. O painel consulta `call_permissions` e, sem permissão, manda o pedido como mensagem livre (só com a janela de 24h aberta). O navegador gera o offer; a answer chega no webhook `connect` (`BUSINESS_INITIATED`), fica criptografada e é entregue uma única vez a quem ligou por `GET /calls/{id}/remote-sdp`. Os status `RINGING`, `ACCEPTED` e `REJECTED` chegam em `value.statuses`.

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
