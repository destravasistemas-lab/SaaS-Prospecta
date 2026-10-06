import { Link } from 'react-router-dom'
import { BRANDING } from '../config/branding'
import LegalLayout, { LegalSection } from '../components/LegalLayout'
import { useI18n } from '../i18n'

export default function Privacy() {
  const { t } = useI18n()
  const email = BRANDING.supportEmail

  return (
    <LegalLayout title={t('Política de Privacidade', 'Privacy Policy')} updated="2026-10-06">
      <LegalSection title={t('1. Quem somos', '1. Who we are')}>
        <p>
          {t(
            `${BRANDING.name} é uma plataforma SaaS operada por ${BRANDING.companyFullName} que permite a empresas gerenciar o atendimento no WhatsApp Business e no Instagram Direct, publicar conteúdo no Instagram e administrar campanhas no Meta Ads. Esta política explica quais dados tratamos, por que e como você pode controlá-los.`,
            `${BRANDING.name} is a SaaS platform operated by ${BRANDING.companyFullName} that lets businesses manage customer service on WhatsApp Business and Instagram Direct, publish content to Instagram and manage Meta Ads campaigns. This policy explains what data we process, why, and how you can control it.`,
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('2. Dados que coletamos', '2. Data we collect')}>
        <p className="font-medium text-[#cbd5e1]">{t('Dados da sua conta na plataforma', 'Your platform account data')}</p>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('Nome, e-mail, nome da empresa e senha (armazenada apenas como hash bcrypt).', 'Name, email, company name and password (stored only as a bcrypt hash).')}</li>
          <li>{t('Dados de assinatura e pagamento processados pelo Asaas (não armazenamos dados de cartão).', 'Subscription and payment data processed by Asaas (we do not store card data).')}</li>
        </ul>
        <p className="font-medium text-[#cbd5e1]">{t('Dados da Plataforma Meta (somente com sua autorização)', 'Meta Platform Data (only with your authorization)')}</p>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('Tokens de acesso da Meta — criptografados em repouso (Fernet/AES-128).', 'Meta access tokens — encrypted at rest (Fernet/AES-128).')}</li>
          <li>{t('WhatsApp: ID da conta WhatsApp Business (WABA), ID e número de telefone, templates de mensagem e mensagens trocadas com seus clientes.', 'WhatsApp: WhatsApp Business Account (WABA) ID, phone number ID and display number, message templates and messages exchanged with your customers.')}</li>
          <li>{t('Instagram: ID e @ da conta profissional, mídias publicadas e métricas (insights), comentários nas suas publicações e mensagens do Direct.', 'Instagram: professional account ID and username, published media and insights, comments on your posts and Direct messages.')}</li>
          <li>{t('Meta Ads: IDs da conta de anúncios e da Página, campanhas, conjuntos, anúncios, métricas e leads de formulários de Lead Ads.', 'Meta Ads: ad account and Page IDs, campaigns, ad sets, ads, metrics and leads from Lead Ads forms.')}</li>
        </ul>
        <p className="font-medium text-[#cbd5e1]">{t('Dados dos seus clientes (contatos)', "Your customers' data (contacts)")}</p>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('Nome público, @ do Instagram, telefone do WhatsApp, e-mail (quando informado), conteúdo das mensagens e registro de consentimento (opt-in/opt-out) para WhatsApp.', 'Public name, Instagram username, WhatsApp phone number, email (when provided), message content and WhatsApp consent record (opt-in/opt-out).')}</li>
        </ul>
        <p>
          {t(
            'Para esses dados, a empresa cliente é a controladora e nós atuamos como operadora, tratando-os apenas conforme as instruções dela.',
            'For this data the business customer is the controller and we act as a processor, handling it only on their instructions.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('3. Como usamos os dados', '3. How we use data')}>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('Exibir e responder conversas do WhatsApp e do Instagram em uma caixa de entrada unificada.', 'Show and answer WhatsApp and Instagram conversations in a unified inbox.')}</li>
          <li>{t('Executar as automações configuradas pela empresa (respostas por palavra-chave, resposta privada a comentários, assistente de IA).', 'Run automations configured by the business (keyword replies, private replies to comments, AI assistant).')}</li>
          <li>{t('Publicar e agendar conteúdo no Instagram e exibir métricas.', 'Publish and schedule Instagram content and show metrics.')}</li>
          <li>{t('Criar, editar e acompanhar campanhas no Meta Ads.', 'Create, edit and track Meta Ads campaigns.')}</li>
        </ul>
        <p>
          {t(
            'Não vendemos dados, não os usamos para publicidade própria ou de terceiros e não usamos Dados da Plataforma Meta para treinar modelos de IA. Usamos os Dados da Plataforma Meta somente para fornecer o serviço à empresa que os autorizou, conforme os Termos da Plataforma Meta.',
            'We do not sell data, do not use it for our own or third-party advertising, and do not use Meta Platform Data to train AI models. We use Meta Platform Data only to provide the service to the business that authorized it, in line with the Meta Platform Terms.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('4. Mensagens no WhatsApp e consentimento', '4. WhatsApp messaging and consent')}>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('Mensagens livres só são enviadas dentro da janela de 24h após a última mensagem do cliente.', "Free-form messages are only sent within the 24-hour window after the customer's last message.")}</li>
          <li>{t('Mensagens iniciadas pela empresa (templates) só vão para contatos com opt-in registrado.', 'Business-initiated messages (templates) only go to contacts with a recorded opt-in.')}</li>
          <li>{t('O contato pode sair a qualquer momento respondendo SAIR / STOP; o opt-out é respeitado automaticamente.', 'Contacts can opt out at any time by replying STOP / SAIR; the opt-out is honored automatically.')}</li>
          <li>{t('Quando o assistente de IA está ativo, ele se identifica como automatizado e transfere para um humano quando solicitado.', 'When the AI assistant is on, it identifies itself as automated and hands off to a human on request.')}</li>
        </ul>
      </LegalSection>

      <LegalSection title={t('5. Compartilhamento e operadores', '5. Sharing and processors')}>
        <p>{t('Compartilhamos dados apenas com provedores necessários para operar o serviço:', 'We share data only with providers needed to run the service:')}</p>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('Meta Platforms (WhatsApp Cloud API, Instagram API, Marketing API) — para executar as ações que você solicita.', 'Meta Platforms (WhatsApp Cloud API, Instagram API, Marketing API) — to perform the actions you request.')}</li>
          <li>{t('Google (Gemini API) — somente se a empresa ativar o assistente de IA, com a chave de API da própria empresa.', "Google (Gemini API) — only if the business enables the AI assistant, using the business's own API key.")}</li>
          <li>{t('Hospedagem e banco de dados (Fly.io / PostgreSQL), armazenamento de mídia (Supabase), e-mail transacional (Resend) e pagamentos (Asaas).', 'Hosting and database (Fly.io / PostgreSQL), media storage (Supabase), transactional email (Resend) and payments (Asaas).')}</li>
        </ul>
        <p>{t('Podemos divulgar dados quando exigido por lei ou ordem judicial.', 'We may disclose data when required by law or court order.')}</p>
      </LegalSection>

      <LegalSection title={t('6. Segurança', '6. Security')}>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('Tráfego criptografado (HTTPS/TLS) e tokens criptografados em repouso.', 'Encrypted traffic (HTTPS/TLS) and tokens encrypted at rest.')}</li>
          <li>{t('Isolamento por empresa (multi-tenant) e controle de acesso por função.', 'Per-business isolation (multi-tenant) and role-based access control.')}</li>
          <li>{t('Webhooks da Meta validados por assinatura HMAC-SHA256.', 'Meta webhooks validated by HMAC-SHA256 signature.')}</li>
        </ul>
      </LegalSection>

      <LegalSection title={t('7. Retenção', '7. Retention')}>
        <p>
          {t(
            'Tokens são mantidos até a desconexão da integração, a remoção do app nas configurações da Meta ou um pedido de exclusão. Mensagens e contatos são mantidos enquanto a conta estiver ativa ou até serem excluídos pela empresa. Após o encerramento da conta, os dados são excluídos em até 30 dias.',
            'Tokens are kept until the integration is disconnected, the app is removed in Meta settings, or deletion is requested. Messages and contacts are kept while the account is active or until the business deletes them. After account closure, data is deleted within 30 days.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('8. Seus direitos e exclusão de dados', '8. Your rights and data deletion')}>
        <p>
          {t(
            'Você pode acessar, corrigir, exportar ou excluir seus dados (LGPD / GDPR). Formas de excluir:',
            'You can access, correct, export or delete your data (LGPD / GDPR). Ways to delete:',
          )}
        </p>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('No app: Conexões Meta → Desconectar (revoga o acesso e apaga o token).', 'In the app: Meta Connections → Disconnect (revokes access and deletes the token).')}</li>
          <li>
            {t('No Facebook/Instagram: Configurações → Apps e sites → remover', 'On Facebook/Instagram: Settings → Apps and websites → remove')} {BRANDING.name}.{' '}
            {t('Recebemos o pedido automaticamente e excluímos os dados.', 'We receive the request automatically and delete the data.')}
          </li>
          <li>{t('Por e-mail', 'By email')}: <a href={`mailto:${email}`} className="text-sky-400 underline">{email}</a></li>
        </ul>
        <p>
          {t('Instruções completas e consulta de status:', 'Full instructions and status lookup:')}{' '}
          <Link to="/data-deletion" className="text-sky-400 underline">{t('Exclusão de Dados', 'Data Deletion')}</Link>
        </p>
      </LegalSection>

      <LegalSection title={t('9. Crianças', '9. Children')}>
        <p>{t('O serviço é destinado a empresas e não é direcionado a menores de 18 anos.', 'The service is intended for businesses and is not directed at anyone under 18.')}</p>
      </LegalSection>

      <LegalSection title={t('10. Alterações e contato', '10. Changes and contact')}>
        <p>
          {t('Avisaremos sobre mudanças relevantes por e-mail ou no app. Dúvidas:', 'We will notify relevant changes by email or in the app. Questions:')}{' '}
          <a href={`mailto:${email}`} className="text-sky-400 underline">{email}</a>
        </p>
      </LegalSection>
    </LegalLayout>
  )
}
