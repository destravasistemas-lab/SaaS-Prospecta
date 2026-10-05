# Deploy do backend no Fly.io

Backend FastAPI do adStudioAI rodando no Fly (região `gru` / São Paulo).
Banco fica **externo** (Supabase/Neon/Render) — o Fly não hospeda o Postgres.

## Pré-requisitos

- [flyctl](https://fly.io/docs/flyctl/install/) instalado
- Conta no Fly (`fly auth signup` ou `fly auth login`)
- Uma URL de **Postgres gerenciado e público** (o banco local do Docker **não**
  é acessível pelo Fly)

## 1. Criar o app (uma vez)

```bash
cd backend
fly auth login
fly apps create adstudioai-backend   # nome deve bater com o fly.toml
```

## 2. Definir os segredos

> Os segredos **não** ficam no `fly.toml` nem na imagem — vão pelo `fly secrets`.
> Se você quer **migrar os dados/tokens atuais**, use o MESMO `FERNET_KEY` e
> `SECRET_KEY` do `.env` local (senão o token do Instagram salvo fica ilegível).

```bash
# Pegue os valores reais do seu backend/.env local (NÃO os coloque neste arquivo).
fly secrets set \
  DATABASE_URL='postgresql+asyncpg://USER:PASS@HOST:5432/DBNAME' \
  FERNET_KEY='<do seu .env>' \
  SECRET_KEY='<do seu .env>' \
  META_APP_ID='<do seu .env>' \
  META_APP_SECRET='<do seu .env>' \
  META_WEBHOOK_VERIFY_TOKEN='<do seu .env>' \
  IG_APP_ID='<do seu .env>' \
  IG_APP_SECRET='<do seu .env>' \
  WHATSAPP_CONFIG_ID='<do seu .env>' \
  APP_URL='https://SEU_FRONTEND' \
  PUBLIC_BASE_URL='https://adstudioai-backend.fly.dev' \
  META_REDIRECT_URI='https://adstudioai-backend.fly.dev/api/v1/auth/meta/callback' \
  IG_REDIRECT_URI='https://adstudioai-backend.fly.dev/api/v1/auth/instagram/callback' \
  CORS_ORIGINS='["https://SEU_FRONTEND"]' \
  ASAAS_API_KEY='<do seu .env>' \
  ASAAS_MODE='sandbox' \
  RESEND_API_KEY='<do seu .env>' \
  -a adstudioai-backend
```

## 3. Deploy

```bash
fly deploy
```

O backend fica em: **https://adstudioai-backend.fly.dev**
Teste: `curl https://adstudioai-backend.fly.dev/health`

## 4. Ajustes pós-deploy

- **Meta/Instagram:** registre os novos redirect URIs (`...fly.dev/...`) no
  painel do Meta App, senão o OAuth falha com *Invalid redirect_uri*.
- **Webhook:** aponte o webhook do Meta/Instagram para
  `https://adstudioai-backend.fly.dev/api/v1/webhook/meta`.
- **Migrations:** rode o Alembic contra o banco de produção uma vez:
  ```bash
  fly ssh console -a adstudioai-backend -C "alembic upgrade head"
  ```

## Comandos úteis

```bash
fly logs -a adstudioai-backend        # logs em tempo real
fly status -a adstudioai-backend      # estado das máquinas
fly secrets list -a adstudioai-backend
fly scale memory 1024 -a adstudioai-backend   # aumentar RAM se precisar
```
