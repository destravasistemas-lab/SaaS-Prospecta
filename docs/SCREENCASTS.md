# Roteiro de screencasts — App Review, permissão por permissão

App: **Destrava** (App ID `2168560223724340`). Os requisitos de cada vídeo vêm da [Permissions Reference](https://developers.facebook.com/docs/permissions/) e do guia de [App Review do WhatsApp](https://developers.facebook.com/documentation/business-messaging/whatsapp/solution-providers/app-review/), consultados em 26/10/2026.

## 1. Validação: o que a Meta pede × o que o sistema faz

| # | Permissão | O vídeo precisa mostrar | Onde está no sistema | Status |
|---|---|---|---|---|
| 1 | `pages_show_list` | Login do Facebook + as Páginas do usuário conectadas ao app | Campaigns → **Facebook Page** (lista e troca de Página) | ✅ ajustado: antes o app pegava a 1ª Página sem mostrar |
| 2 | `business_management` | Login do Facebook + dados de desempenho de anúncios (impressões, gasto, cliques, alcance) | Campaigns → seletor de conta agrupado por **portfólio empresarial** + métricas | ✅ ajustado: antes não havia chamada a `/me/businesses` |
| 3 | `pages_manage_metadata` | Login + o usuário inscrevendo a Página em webhooks | Campaigns → Facebook Page → **Lead Ads webhook: Subscribe** | ✅ ajustado: antes era automático e invisível |
| 4 | `pages_read_engagement` | Login + conteúdo de um post da Página exibido no app | Campaigns → **Recent Page posts** | ✅ ajustado: antes o app só lia posts do Instagram |
| 5 | `pages_manage_ads` | Login + criar um anúncio para a Página, com sucesso | Campanha → ad set → **New ad** (inclusive "FB post") | ✅ |
| 6 | `ads_management` | Login + dados de desempenho (impressões, conversões, gasto, cliques, alcance) | Campaigns (painel de métricas) + criar/pausar/duplicar | ✅ |
| 7 | `ads_read` | Sem requisito específico ("ver App Review docs") → mostrar relatórios | Campaigns + detalhe da campanha (por nível e breakdown) | ✅ |
| 8 | `leads_retrieval` | Sem requisito específico → mostrar o lead do formulário chegando | Leads (selo **Ad**) + "Leads by ad" em Campaigns | ✅ |
| 9 | `instagram_business_basic` | Login do Instagram + username e ID da conta no app | Publish & Automation → **cabeçalho do perfil** | ✅ ajustado: antes só aparecia o ID |
| 10 | `instagram_business_content_publish` | Login + criar post de foto com legenda/hashtags e publicar no feed | Publish & Automation → Publish now | ✅ |
| 11 | `instagram_business_manage_comments` | Login + **criar, atualizar e excluir** comentário, no app e no Instagram | Media & Insights → **Manage comments** | ✅ ajustado: antes só havia resposta automática |
| 12 | `instagram_business_manage_messages` | Login + enviar DM pelo app e mostrar chegando no Instagram + cURL do API Integration Helper | Direct Messages | ✅ (o cURL é feito no App Dashboard) |
| 13 | `instagram_business_manage_insights` | Login + insights da conta e das mídias | Media & Insights | ✅ |
| 14 | `whatsapp_business_management` | Criar um template de mensagem no app (ou no WhatsApp Manager) | Templates → New Template | ✅ |
| 15 | `whatsapp_business_messaging` | Enviar mensagem pelo app e o WhatsApp (celular ou web) recebendo | Customer Service → WhatsApp | ✅ |
| 16 | `public_profile` | Nada: aprovação automática | — | ✅ |
| 17 | Marketing API Access Tier | Sem vídeo: precisa de volume de chamadas (500 em 15 dias, erro < 15%) | Uso real de Campaigns | ⏳ depende de uso |

"Atualizar" comentário: a API do Instagram não edita o texto de um comentário. O equivalente é **ocultar/reexibir** (`POST /{comment-id}?hide=`), que é o que o app oferece. Diga isso na legenda e no texto do formulário.

## 2. Antes de gravar

**Configuração do vídeo**
- App em **English** (🇺🇸 no rodapé da sidebar ou na tela de login).
- Largura máxima de 1440 px (1280×720 é o ideal), zoom do navegador em 100%, **cursor grande** (Windows: Configurações → Acessibilidade → Ponteiro do mouse → tamanho 3).
- **Sem áudio.** Legendas em inglês na tela (o Clipchamp, que vem no Windows 11, faz isso), uma por passo.
- Um arquivo MP4 por permissão, com o nome da permissão. Não junte duas permissões no mesmo vídeo: a Meta rejeita.
- Cada vídeo começa no login do app (e-mail e senha) e mostra o login da Meta com a tela de permissões. Pode gravar o login uma vez por bloco e reaproveitar o trecho no início de cada vídeo do bloco.

**Forçar a tela de consentimento completa** (senão a Meta pula direto e o vídeo não mostra a concessão)
- Facebook: [facebook.com/settings?tab=business_tools](https://www.facebook.com/settings?tab=business_tools) → remova **Destrava** → no app, Meta Connections → Disconnect em Meta Ads.
- Instagram: [instagram.com/accounts/manage_access](https://www.instagram.com/accounts/manage_access/) → remova o app → no app, Disconnect em Instagram.

**Material pronto**
- Página do Facebook com pelo menos 2 posts com imagem.
- Conta de anúncios num portfólio empresarial, com 1 campanha que já teve gasto (as métricas não podem estar zeradas).
- Formulário de Lead Ads na Página e o [Lead Ads Testing Tool](https://developers.facebook.com/tools/lead-ads-testing) aberto.
- Instagram profissional com 1 post e uma **segunda conta** do Instagram (para comentar e mandar DM).
- Segundo celular com WhatsApp, que tenha mandado uma mensagem para o número da empresa nas últimas 24 h.
- Uma imagem JPEG para publicar.

**Depois de gravar:** cada vídeo gera a chamada de API que o `api_precheck` exige (pelo menos 1 por permissão nos últimos 30 dias). O painel atualiza em até 48 h. Só envie quando todas estiverem verdes.

## 3. Bloco A — Meta Ads (Facebook Login for Business)

Login comum a todos os vídeos do bloco:
1. `prospecta.sistemasdestrava.com.br/login` → e-mail e senha → **Sign in**.
2. Sidebar → **Meta Connections** → card **Meta Ads** → **Connect**.
3. Popup da Meta: entrar no Facebook → escolher o portfólio, as Páginas e a conta de anúncios → mostrar a lista de permissões → **Save / Continue**.
4. Volta ao app: card **Meta Ads** com status **Connected**.

Legenda: *"The business owner logs in with Facebook Login for Business and grants the requested permissions."*

### 3.1 `pages_show_list`
**Roteiro**
1. Login comum (passos 1–4).
2. Sidebar → **Campaigns** → role até o card **Facebook Page**.
3. Abra o seletor: aparecem as Páginas que o usuário gerencia (nome, categoria, ID e "N Page(s) you manage").
4. Escolha outra Página e mostre o nome e a foto atualizando.

**Legendas:** *"The app lists the Facebook Pages this user manages (GET /me/accounts)."* → *"The user picks the Page used for ads and Lead Ads forms."*

**How will this permission be used?**
> Destrava is a marketing platform for small businesses. After a business connects Meta Ads with Facebook Login for Business, we call GET /me/accounts to list the Facebook Pages the user manages and show them in Campaigns → Facebook Page, where the user chooses which Page their ads and Lead Ads forms use. We only display the Page name, picture, category and ID. pages_show_list is also required as a dependency of pages_read_engagement, pages_manage_metadata and pages_manage_ads, which we use to show Page posts, receive Lead Ads webhooks and create ads for the Page.

### 3.2 `business_management`
**Roteiro**
1. Login comum.
2. **Campaigns** → clique no seletor de conta de anúncios (ícone de prédio, no topo).
3. Mostre os grupos **"Business: <nome do portfólio>"** com as contas próprias e as de cliente (marcadas "client").
4. Troque de conta → as métricas (Spend, Impressions, Reach, Clicks, Results) recarregam.

**Legendas:** *"Ad accounts are grouped by business portfolio (owned and client accounts)."* → *"Choosing an account loads its ads performance data."*

**How will this permission be used?**
> Many of our customers are agencies and businesses whose ad accounts belong to a business portfolio or are shared with them as client ad accounts. We use business_management to call GET /me/businesses and read each portfolio's owned_ad_accounts and client_ad_accounts, so the user can choose the right ad account in Campaigns, grouped by portfolio. After choosing an account, the app loads that account's campaigns and performance data (spend, impressions, reach, clicks, results). We do not create or modify business portfolios, people or assets.

### 3.3 `pages_manage_metadata`
**Roteiro**
1. Login comum.
2. **Campaigns** → card **Facebook Page** → mostre **Lead Ads webhook: Subscribed**.
3. Clique **Unsubscribe** → status muda para **Not subscribed**.
4. Clique **Subscribe** → volta para **Subscribed**.
5. (Opcional, reforça o uso) mande um lead pelo Lead Ads Testing Tool e mostre-o chegando em **Leads**.

**Legendas:** *"The user subscribes their Page to our app's leadgen webhook (POST /{page-id}/subscribed_apps)."* → *"New Lead Ads leads now reach the app in real time."*

**How will this permission be used?**
> We use pages_manage_metadata only to subscribe our app to the leadgen webhook of the Page the business selected (POST /{page-id}/subscribed_apps). When someone submits the business's Lead Ads instant form, Meta notifies our webhook and the lead appears in the business's Leads list in real time. In Campaigns → Facebook Page the user sees the webhook status and can subscribe or unsubscribe the Page. We do not change any other Page setting.

### 3.4 `pages_read_engagement`
**Roteiro**
1. Login comum.
2. **Campaigns** → card **Facebook Page** → seção **Recent Page posts**: imagem, texto e data de cada post.
3. Clique no ícone ↗ de um post → abre o mesmo post no Facebook (mostre que o conteúdo é igual).

**Legendas:** *"Posts published by the business's Page are read and displayed in the app."* → *"Same post on Facebook."*

**How will this permission be used?**
> We use pages_read_engagement to read the posts published by the business's own Facebook Page (GET /{page-id}/published_posts: message, picture, permalink and date). They are shown in Campaigns → Facebook Page → Recent Page posts and in the ad creator ("FB post"), so the business can pick an existing post to promote. We do not read or store personal data of the Page's followers.

### 3.5 `pages_manage_ads`
**Roteiro**
1. Login comum.
2. **Campaigns** → abra uma campanha → no ad set, **New ad**.
3. Escolha **FB post** → selecione um post da Página → nome do anúncio → **Create ad (paused)**.
4. O anúncio aparece na lista com status **Paused**.
5. (Reforço) abra o Gerenciador de Anúncios da Meta e mostre o mesmo anúncio criado, com a Página como identidade.

**Legendas:** *"The business creates an ad for its Facebook Page."* → *"Ad created successfully (paused for review before spending)."*

**How will this permission be used?**
> We use pages_manage_ads to create ads on behalf of the business's Facebook Page. Inside a campaign's ad set, the user clicks New ad and chooses an image, video, carousel or an existing Page post; we create the ad creative with the Page as the identity (object_story_spec or object_story_id) and then the ad. Ads are always created paused, so the business reviews them before any spend.

### 3.6 `ads_management`
**Roteiro**
1. Login comum.
2. **Campaigns** → painel de métricas: **Spend, Results, Cost / result, ROAS, Reach, Impressions, Clicks, CTR, CPC, CPM**. Troque 7 / 30 / 90 days.
3. **New Campaign** → nome, objetivo, **Special ad category** → **Create Campaign** (criada pausada).
4. Na lista: **Activate/Pause** e **Duplicate** numa campanha.

**Legendas:** *"Ads performance data from the Insights API: impressions, results, spend, clicks, reach."* → *"The business creates and manages its own campaigns."*

**How will this permission be used?**
> Businesses manage their own Meta ad campaigns in our app: they create campaigns (declaring Special Ad Categories when applicable), ad sets (budget, schedule, targeting) and ads, and pause, activate, duplicate or delete them. Everything is created paused. The Campaigns dashboard shows performance data from the Insights API (spend, impressions, reach, frequency, clicks, CTR, CPC, CPM, results, cost per result and ROAS) for 7, 30 or 90 days.

### 3.7 `ads_read`
**Roteiro**
1. Login comum.
2. **Campaigns** → painel de métricas (sem criar nada, foco em leitura).
3. Abra uma campanha → desempenho por ad set/anúncio e o breakdown por idade, gênero, plataforma, dispositivo ou região.
4. Volte e mostre **Leads by ad**.

**Legendas:** *"Read-only reporting: campaign, ad set and ad insights with breakdowns."*

**How will this permission be used?**
> We use ads_read for reporting on the business's own ad accounts: we list ad accounts, campaigns, ad sets and ads and read Insights (spend, impressions, reach, clicks, results, CTR, CPM, ROAS), shown on the Campaigns dashboard and on each campaign's detail page with breakdowns by age, gender, platform, device and region. Leads received from each ad are matched to the ad name so the business sees which ads generate customers.

### 3.8 `leads_retrieval`
**Roteiro**
1. Login comum.
2. **Campaigns** → card Facebook Page com **Lead Ads webhook: Subscribed**.
3. Em outra aba, o **Lead Ads Testing Tool**: escolha a Página e o formulário → **Create lead**.
4. Volte ao app → **Leads** → o lead novo aparece com nome, telefone/e-mail e selo **Ad**.

**Legendas:** *"A person submits the business's Lead Ads form."* → *"The lead is retrieved (GET /{leadgen-id}) and added to the business's Leads list."*

**How will this permission be used?**
> When a person submits the business's Lead Ads instant form, our webhook receives the leadgen_id and we call GET /{leadgen-id} to read the submitted fields (such as name, email and phone). The lead is saved in that business's Leads list with the source "Ad" and attributed to the ad that generated it, so the team can contact the lead quickly. Leads are stored only for the business that owns the form and can be deleted at any time.

## 4. Bloco B — Instagram (Business Login for Instagram)

Login comum:
1. Login no app → **Meta Connections** → card **Instagram** → **Connect**.
2. Popup do Instagram: entrar → mostrar as permissões → **Allow**.
3. Volta ao app: card **Instagram** com **Connected**.

Legenda: *"The business logs in with Instagram and grants the requested permissions."*

### 4.1 `instagram_business_basic`
**Roteiro**
1. Login comum.
2. Sidebar → **Publish & Automation** → cabeçalho com foto, **@username**, nome, **Account ID**, tipo de conta, seguidores e posts.

**Legenda:** *"Basic profile metadata of the connected Instagram professional account: username and ID."*

**How will this permission be used?**
> After the business connects its Instagram professional account with Business Login for Instagram, we read its profile (ID, username, name, account type, profile picture, followers and media count) to show which account is connected on the Publish & Automation screen and to route comment and Direct message webhooks to the right business. It is also the base permission for publishing, comments, messages and insights.

### 4.2 `instagram_business_content_publish`
**Roteiro**
1. Login comum.
2. **Publish & Automation** → Media Type **Image** → upload do JPEG.
3. **Caption** com texto e hashtags → **Publish Now** → mensagem "Published now!".
4. Abra o Instagram (app ou web) → o post aparece no feed com a mesma legenda.

**Legendas:** *"The business creates a photo post with caption and hashtags."* → *"Published to the business's Instagram feed."*

**How will this permission be used?**
> Businesses publish photos and videos/Reels to their own Instagram professional account from Publish & Automation: they upload the media, write the caption and hashtags and click Publish now, or schedule it up to 15 days ahead. We create the media container and publish it via /media and /media_publish. Nothing is published without the user's explicit action.

### 4.3 `instagram_business_manage_comments`
**Roteiro**
1. Login comum.
2. Com a segunda conta, comente no post da empresa (pelo celular).
3. **Publish & Automation** → aba **Media & Insights** → no post, **Manage comments**.
4. **Criar:** escreva no campo de baixo → **Comment**.
5. **Responder:** ícone ↩ no comentário da segunda conta → texto → **Reply**.
6. **Atualizar:** ícone 👁 → **Hide** (fica "Hidden") → depois **Unhide**.
7. **Excluir:** 🗑 no comentário criado no passo 4 → confirmar.
8. Abra o post no app do Instagram e mostre cada resultado (comentário novo, resposta, oculto, excluído).

**Legendas:** *"Create a new comment."* → *"Reply to a comment."* → *"Update: hide / unhide (the Instagram API does not edit comment text)."* → *"Delete a comment."* → *"Result in the native Instagram app."*

**How will this permission be used?**
> Businesses moderate comments on their own Instagram posts: in Media & Insights → Manage comments they read comments and replies, post a new comment, reply to a comment, hide or unhide it, and delete it. Hiding/unhiding is how a comment is updated, since the API does not allow editing comment text. Businesses can also set keyword automations: when someone comments a chosen keyword on a selected post, we reply publicly to that comment once.

### 4.4 `instagram_business_manage_messages`
**Roteiro**
1. Login comum.
2. Da segunda conta, mande "Hi" no Direct da empresa (abre a janela de 24 h).
3. Sidebar → **Direct Messages** → a conversa aparece → responda pelo app.
4. Mostre a resposta chegando no Instagram da segunda conta (gravação, não print).
5. App Dashboard → Instagram → **API Integration Helper** → gere o cURL de envio de mensagem e mostre a resposta com `message_id`.

**Legendas:** *"Direct messages are read and answered from the app."* → *"Message received in the Instagram inbox."* → *"cURL generated in the API Integration Helper."*

**How will this permission be used?**
> Our inbox lets businesses read and reply to Instagram Direct messages from their customers on the Direct Messages screen. Replies are sent with the Send API only within 24 hours of the customer's last message. For keyword comments we send one Private Reply per comment, within 7 days. An optional AI assistant answers only about the business, identifies itself as automated and hands the conversation to a human on request.

### 4.5 `instagram_business_manage_insights`
**Roteiro**
1. Login comum.
2. **Publish & Automation** → **Media & Insights** → bloco de métricas da conta (reach, views, profile views, website clicks — últimos 30 dias).
3. **Recent Stories** (reach, impressions, replies, taps) e **Recent Media** (curtidas e comentários por post).

**Legenda:** *"Insights of the connected professional account and its media."*

**How will this permission be used?**
> Businesses see insights for their own professional account in Media & Insights: reach, views, profile views and website clicks for the last 30 days, insights for recent stories (reach, impressions, replies, taps) and likes and comments for each recent post. Insights are read only for the connected account and are never shared with third parties.

## 5. Bloco C — WhatsApp (Embedded Signup)

### 5.1 `whatsapp_business_management`
**Roteiro**
1. Login no app → **Meta Connections** → **WhatsApp Business** → **Connect** → fluxo do Embedded Signup (portfólio, WABA, número) → **WhatsApp Business connected!**
2. Sidebar → **Templates** → **New Template**: nome, categoria (Utility ou Marketing), idioma, corpo com variável `{{1}}` e exemplo → **Submit for approval**.
3. O template aparece na lista como **PENDING** → **Sync** atualiza o status.

**Legendas:** *"The business connects its WhatsApp Business Account with Embedded Signup."* → *"The business creates a message template and submits it for approval."*

**How will this permission be used?**
> Businesses connect their WhatsApp Business Account through Embedded Signup. We use whatsapp_business_management to subscribe our app to the WABA's webhooks, read its phone numbers, and let the business create, submit for approval, sync and delete its own message templates on the Templates screen, where the template status is shown.

### 5.2 `whatsapp_business_messaging`
**Roteiro**
1. Login no app → **Meta Connections** (WhatsApp **Connected**).
2. Do segundo celular, mande "Hi" para o número da empresa.
3. **Customer Service → WhatsApp** → a conversa aparece → responda pelo app.
4. Mostre o celular recebendo a resposta (grave a tela do celular ou filme com a câmera).

**Legendas:** *"Customer message received via webhook."* → *"Reply sent from the app within the 24-hour window."* → *"Message delivered on the WhatsApp client."*

**How will this permission be used?**
> Businesses answer their customers from a shared WhatsApp inbox (Customer Service → WhatsApp). Incoming messages arrive via webhook; agents reply with free-form messages only within the 24-hour customer service window. Outside the window only approved templates can be sent, and only to contacts with a recorded opt-in; STOP/SAIR opt-out keywords are honored automatically. We also register the business phone number on the Cloud API once, with the business's own PIN.

## 6. Envio
1. App Review → Requests → para cada permissão: cole o texto acima e anexe o vídeo correspondente.
2. **App verification details:** e-mail e senha de um usuário de teste do app, mais: *"Log in at https://prospecta.sistemasdestrava.com.br/login. Meta Connections shows the three integrations; Campaigns, Publish & Automation, Direct Messages, WhatsApp and Templates are in the sidebar. The language switch (🇺🇸) is in the sidebar footer."*
3. Confira o `api_precheck` verde para todas e envie (não deixe em Draft).
