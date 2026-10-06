import { Link } from 'react-router-dom'
import { BRANDING } from '../config/branding'
import LegalLayout, { LegalSection } from '../components/LegalLayout'
import { useI18n } from '../i18n'

export default function Terms() {
  const { t } = useI18n()
  const email = BRANDING.supportEmail

  return (
    <LegalLayout title={t('Termos de Serviço', 'Terms of Service')} updated="2026-10-06">
      <LegalSection title={t('1. Aceitação', '1. Acceptance')}>
        <p>
          {t(
            `Ao criar uma conta ou usar o ${BRANDING.name}, você concorda com estes Termos e com a nossa Política de Privacidade, em nome próprio e da empresa que representa.`,
            `By creating an account or using ${BRANDING.name}, you agree to these Terms and to our Privacy Policy, on your own behalf and on behalf of the business you represent.`,
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('2. O serviço', '2. The service')}>
        <p>
          {t(
            'Fornecemos ferramentas para atendimento no WhatsApp Business e no Instagram Direct, publicação no Instagram, automações e gestão de campanhas no Meta Ads, usando as APIs oficiais da Meta.',
            'We provide tools for customer service on WhatsApp Business and Instagram Direct, Instagram publishing, automations and Meta Ads campaign management, using Meta’s official APIs.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('3. Políticas da Meta', '3. Meta policies')}>
        <p>{t('Você é responsável por cumprir as políticas da Meta, incluindo:', 'You are responsible for complying with Meta policies, including:')}</p>
        <ul className="list-disc list-inside space-y-1">
          <li>
            <a href="https://www.whatsapp.com/legal/business-policy" target="_blank" rel="noopener noreferrer" className="text-sky-400 underline">
              {t('Política Comercial e de Mensagens do WhatsApp', 'WhatsApp Business & Messaging Policy')}
            </a>
          </li>
          <li>
            <a href="https://www.facebook.com/policies/commerce" target="_blank" rel="noopener noreferrer" className="text-sky-400 underline">
              {t('Políticas de Comércio da Meta', 'Meta Commerce Policies')}
            </a>
          </li>
          <li>
            <a href="https://transparency.meta.com/policies/ad-standards/" target="_blank" rel="noopener noreferrer" className="text-sky-400 underline">
              {t('Padrões de Publicidade da Meta', 'Meta Advertising Standards')}
            </a>
          </li>
          <li>
            <a href="https://help.instagram.com/581066165581870" target="_blank" rel="noopener noreferrer" className="text-sky-400 underline">
              {t('Termos de Uso do Instagram', 'Instagram Terms of Use')}
            </a>
          </li>
        </ul>
        <p>
          {t(
            'Em especial: obtenha opt-in antes de enviar mensagens iniciadas pela empresa, respeite pedidos de saída (opt-out), não envie spam e não promova produtos ou serviços proibidos. Podemos suspender contas que violem essas políticas.',
            'In particular: obtain opt-in before sending business-initiated messages, honor opt-out requests, do not send spam and do not promote prohibited products or services. We may suspend accounts that violate these policies.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('4. Sua conta', '4. Your account')}>
        <p>
          {t(
            'Mantenha suas credenciais em sigilo e conceda acesso apenas a membros da equipe autorizados. Você é responsável pelas ações realizadas na sua conta.',
            'Keep your credentials confidential and grant access only to authorized team members. You are responsible for actions taken in your account.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('5. Conteúdo e dados', '5. Content and data')}>
        <p>
          {t(
            'Você mantém a propriedade do seu conteúdo e dos dados dos seus clientes. Tratamos esses dados apenas para prestar o serviço, conforme a Política de Privacidade.',
            'You keep ownership of your content and your customers’ data. We process that data only to provide the service, as described in the Privacy Policy.',
          )}{' '}
          <Link to="/privacy" className="text-sky-400 underline">{t('Política de Privacidade', 'Privacy Policy')}</Link>
        </p>
      </LegalSection>

      <LegalSection title={t('6. Assistente de IA', '6. AI assistant')}>
        <p>
          {t(
            'O assistente de IA é opcional, limitado ao atendimento da sua empresa e se identifica como automatizado. Revise as respostas e a base de conhecimento que você fornece; você é responsável pelas informações comunicadas aos seus clientes.',
            'The AI assistant is optional, limited to your business’s customer service and identifies itself as automated. Review the answers and the knowledge base you provide; you are responsible for the information communicated to your customers.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('7. Planos e pagamentos', '7. Plans and payments')}>
        <p>
          {t(
            'Os planos pagos são cobrados de forma recorrente via Asaas. Custos de conversas do WhatsApp e de anúncios são cobrados diretamente pela Meta à sua conta.',
            'Paid plans are billed on a recurring basis via Asaas. WhatsApp conversation costs and ad spend are billed directly by Meta to your account.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('8. Encerramento', '8. Termination')}>
        <p>
          {t(
            'Você pode cancelar a qualquer momento. Podemos suspender ou encerrar contas que violem estes Termos ou as políticas da Meta. Após o encerramento, os dados são excluídos em até 30 dias.',
            'You may cancel at any time. We may suspend or terminate accounts that violate these Terms or Meta policies. After termination, data is deleted within 30 days.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('9. Limitação de responsabilidade', '9. Limitation of liability')}>
        <p>
          {t(
            'O serviço é fornecido "como está". Não nos responsabilizamos por indisponibilidades ou mudanças das APIs da Meta, nem por danos indiretos, na máxima extensão permitida pela lei.',
            'The service is provided "as is". We are not liable for unavailability of or changes to Meta APIs, nor for indirect damages, to the maximum extent permitted by law.',
          )}
        </p>
      </LegalSection>

      <LegalSection title={t('10. Contato', '10. Contact')}>
        <p>
          <a href={`mailto:${email}`} className="text-sky-400 underline">{email}</a>
        </p>
      </LegalSection>
    </LegalLayout>
  )
}
