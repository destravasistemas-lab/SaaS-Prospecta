# Meta App Review / Tech Provider — guia de submissão

## 1. Configuração no App Dashboard

| Campo | Valor |
|---|---|
| Privacy Policy URL | `https://SEU_DOMINIO/privacy` |
| Terms of Service URL | `https://SEU_DOMINIO/terms` |
| User data deletion → Data Deletion Callback URL | `https://API_DOMINIO/api/v1/privacy/data-deletion` |
| Deauthorize Callback URL | `https://API_DOMINIO/api/v1/privacy/deauthorize` |
| Webhook (WhatsApp + Instagram) | `https://API_DOMINIO/api/v1/webhook/meta` |
| Facebook Login redirect URI | `https://API_DOMINIO/api/v1/auth/meta/callback` |
| Instagram Login redirect URI | `https://API_DOMINIO/api/v1/auth/instagram/callback` |
| App icon / categoria / e-mail de contato | `contato@destravasistemas.com.br` |

Webhook fields: WhatsApp → `messages`; Instagram → `messages`, `comments`; Page → `leadgen`.

`.env` do backend: `APP_URL` (frontend público), `SUPPORT_EMAIL`, `WHATSAPP_CONFIG_ID`, `META_APP_SECRET`, `IG_APP_SECRET`.

## 2. Permissões solicitadas (somente as usadas)

| Permissão | Onde aparece no app |
|---|---|
| `whatsapp_business_management` | Conexões Meta → WhatsApp (Embedded Signup), Templates (criar/sincronizar) |
| `whatsapp_business_messaging` | WhatsApp (inbox), envio de template com opt-in, Follow-ups |
| `instagram_business_basic` | Conexões Meta → Instagram (mostra @ conectado) |
| `instagram_business_manage_messages` | Instagram Direct (inbox), resposta privada a comentário |
| `instagram_business_manage_comments` | Publicar & Automação → automação de comentário |
| `instagram_business_content_publish` | Publicar & Automação → publicar/agendar |
| `instagram_business_manage_insights` | Publicar & Automação → Mídias & Métricas |
| `ads_management`, `ads_read` | Campanhas (criar/pausar/duplicar/excluir, métricas) |
| `business_management` | Listar contas de anúncios do Business |
| `pages_show_list`, `pages_read_engagement` | Página dos anúncios / impulsionar post |
| `leads_retrieval` | Leads de formulários de Lead Ads chegam em Leads |

Removidos nesta versão: `/auth/meta/login` legado (pedia `instagram_basic`, `instagram_content_publish`, `pages_manage_metadata` sem uso) e `pages_show_list` do fluxo de WhatsApp.

## 3. Roteiro do vídeo (gravar com o app em **English** — seletor 🇺🇸 no rodapé da sidebar ou na tela de login)

Grave um vídeo por permissão (ou um vídeo com capítulos). Mostre sempre: login → tela → ação → resultado no app/cliente.

1. **Login e consentimento** — Landing → Sign up (mostre o aceite de Terms/Privacy) → Sign in.
2. **Meta Connections** — abra "Permissions requested and why" de cada card.
3. **WhatsApp Embedded Signup** — Connect WhatsApp → fluxo da Meta → "WhatsApp Business connected!".
4. **whatsapp_business_messaging** — de outro celular, mande "Hi" para o número → mensagem aparece no inbox → responda (janela 24h ativa) → mostre a resposta chegando no celular.
5. **Opt-in e template** — Leads → clique em "No opt-in" de um contato → confirme → WhatsApp → Send template (marque a confirmação de opt-in) → template chega.
6. **Opt-out** — no celular envie `STOP` → resposta automática de confirmação → em Leads o contato fica "Opt-out" → Templates → Broadcast mostra que ele é excluído.
7. **whatsapp_business_management** — Templates → New Template → Submit for approval → Sync.
8. **Instagram Login** — Connect Instagram → autorizar → conectado.
9. **content_publish** — Publish & Automation → upload de imagem → Publish Now → mostre o post no Instagram.
10. **manage_comments + manage_messages** — ative a automação de comentário com palavra-chave → de outra conta comente a palavra → resposta pública + Private Reply no Direct → responda no Direct → aparece em Direct Messages → responda pelo app.
11. **manage_insights** — aba Media & Insights.
12. **Ads** — Connect Meta Ads → Campaigns → New Campaign (mostre "Special ad category") → criada pausada → abra → New ad set → New ad → pause/duplicate/delete.
13. **leads_retrieval** — envie um lead pelo Lead Ads Testing Tool → aparece em Leads com selo "Ad".
14. **Desconectar / exclusão** — Meta Connections → Disconnect; página `/data-deletion`.

## 4. Textos para o formulário (cole em inglês)

**whatsapp_business_messaging** — Our platform lets businesses answer their customers on WhatsApp from a shared team inbox. We receive messages through webhooks and send free-form replies only inside the 24-hour customer service window. Outside the window, agents can only send Meta-approved templates to contacts with a recorded opt-in. Opt-out keywords (STOP/SAIR) are honored automatically.

**whatsapp_business_management** — Used after Embedded Signup to subscribe our app to the business's WABA webhooks, register the phone number and let the business create, sync and delete its own message templates.

**instagram_business_manage_messages** — Businesses read and reply to Instagram Direct messages in our inbox, only within 24 hours of the user's last message. For keyword comments we send exactly one Private Reply per comment.

**instagram_business_manage_comments** — Businesses configure keyword automations; when a user comments the keyword on a selected post, we reply publicly to that comment and send a Private Reply.

**instagram_business_content_publish** — Businesses publish or schedule (up to 15 days) image and video posts to their own professional account.

**instagram_business_manage_insights** — We show the business its own account and media insights (reach, impressions, engagement).

**ads_management / ads_read** — Businesses create, pause, duplicate and delete campaigns, ad sets and ads in their own ad accounts (always created paused, with Special Ad Category declaration) and see performance metrics.

**leads_retrieval** — Leads submitted on the business's Lead Ads forms are delivered by webhook and added to the business's lead list.

## 5. O que foi corrigido para conformidade

- Endpoints de OAuth/conexões exigiam `account_id` sem autenticação (qualquer pessoa podia desconectar a conta de outro cliente) → agora usam o usuário autenticado.
- Callback de exclusão de dados só gerava código (TODO) → agora exclui tokens, IDs e leads/conversas do usuário e expõe status real em `/data-deletion`.
- Tokens de acesso e payloads com dados pessoais eram gravados em log → removido.
- Envio livre no WhatsApp (`/whatsapp/send`, interativo) ignorava a janela de 24h → bloqueado fora da janela.
- Disparo em massa ia para todos os leads com telefone → só para opt-in; opt-out por palavra-chave.
- Instagram DM sem verificação de janela de 24h → bloqueado fora da janela.
- IA com regras fixas: escopo restrito ao negócio, identifica-se como automatizada, transfere para humano.
- Campanhas com Categoria Especial de Anúncio.
- Landing sem alegações de parceria/"plataforma oficial" e com aviso de marcas da Meta.
- Botão "Continuar com Google" sem função removido; tela de Configurações agora funcional.
