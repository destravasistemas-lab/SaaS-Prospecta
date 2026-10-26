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
| `instagram_business_basic` | Publicar & Automação → cabeçalho do perfil (@username, ID, seguidores) |
| `instagram_business_manage_messages` | Instagram Direct (inbox), resposta privada a comentário |
| `instagram_business_manage_comments` | Mídias & Métricas → Gerenciar comentários (comentar, responder, ocultar, excluir) + automação de comentário |
| `instagram_business_content_publish` | Publicar & Automação → publicar/agendar |
| `instagram_business_manage_insights` | Publicar & Automação → Mídias & Métricas |
| `ads_management`, `ads_read` | Campanhas (criar/pausar/duplicar/excluir, métricas e breakdowns) |
| `business_management` | Campanhas → seletor de conta agrupado por portfólio (`/me/businesses`) |
| `pages_show_list` | Campanhas → Página do Facebook (lista e troca de Página) |
| `pages_read_engagement` | Campanhas → posts recentes da Página; anúncio "Post FB" |
| `pages_manage_metadata` | Campanhas → Página do Facebook → webhook de Lead Ads (inscrever/cancelar) |
| `pages_manage_ads` | Criar anúncios com a Página como identidade (inclusive impulsionar post da Página) |
| `leads_retrieval` | Leads de formulários de Lead Ads chegam em Leads |

Removidos nesta versão: `/auth/meta/login` legado (pedia `instagram_basic` e `instagram_content_publish` via Facebook Login, sem uso) e `pages_show_list` do fluxo de WhatsApp.

## 3. Roteiro dos vídeos e textos do formulário

Estão em [SCREENCASTS.md](SCREENCASTS.md): validação de cada permissão contra o requisito da Meta, roteiro clique a clique, legendas em inglês e o texto de "How will this permission be used?" de cada uma.

## 4. O que foi corrigido para conformidade

- Endpoints de OAuth/conexões exigiam `account_id` sem autenticação (qualquer pessoa podia desconectar a conta de outro cliente) → agora usam o usuário autenticado.
- Callback de exclusão de dados só gerava código (TODO) → agora exclui tokens, IDs e leads/conversas do usuário e expõe status real em `/data-deletion`.
- Tokens de acesso e payloads com dados pessoais eram gravados em log → removido.
- Envio livre no WhatsApp (`/whatsapp/send`, interativo) ignorava a janela de 24h → bloqueado fora da janela.
- Disparo em massa ia para todos os leads com telefone → só para opt-in; opt-out por palavra-chave.
- Follow-up automático (só WhatsApp): template aprovado, uma vez por envio, só opt-in, janela de horário configurável.
- Instagram DM sem verificação de janela de 24h → bloqueado fora da janela.
- IA com regras fixas: escopo restrito ao negócio, identifica-se como automatizada, transfere para humano.
- Campanhas com Categoria Especial de Anúncio.
- Landing sem alegações de parceria/"plataforma oficial" e com aviso de marcas da Meta.
- Botão "Continuar com Google" sem função removido; tela de Configurações agora funcional.
- Telas para o App Review: Página do Facebook (lista, troca, webhook de Lead Ads, posts), contas agrupadas por portfólio, impulsionar post da Página, moderação de comentários do Instagram e cabeçalho do perfil.
