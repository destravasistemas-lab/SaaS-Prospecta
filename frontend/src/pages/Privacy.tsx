export default function Privacy() {
  return (
    <div className="min-h-screen bg-[#0a0a0f] text-[#e2e2e8] px-6 py-12">
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-white">Política de Privacidade</h1>
          <p className="text-[#555] text-sm mt-2">adStudioAI — última atualização: 19 de junho de 2026</p>
        </div>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-white">Dados coletados</h2>
          <ul className="text-[#555] text-sm space-y-1 list-disc list-inside">
            <li>ID e nome da Página do Facebook / conta Instagram conectada</li>
            <li>Tokens de acesso Meta (armazenados criptografados)</li>
            <li>ID da conta de anúncios (quando conectada)</li>
            <li>ID da conta WhatsApp Business (quando conectada)</li>
            <li>Leads capturados via comentários e DMs do Instagram (nome, @, e-mail e telefone opcionais)</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-white">Como usamos os dados</h2>
          <p className="text-[#555] text-sm">
            Os dados são usados exclusivamente para fornecer os serviços do adStudioAI ao titular da conta:
            automação de respostas, captura de leads, publicação de conteúdo e análise de campanhas de anúncios.
            Nenhum dado é vendido ou compartilhado com terceiros.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-white">Retenção de dados</h2>
          <p className="text-[#555] text-sm">
            Os tokens de acesso são mantidos até que o usuário desconecte a integração ou solicite exclusão.
            Leads são mantidos até serem excluídos pelo titular da conta.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-white">Exclusão de dados</h2>
          <p className="text-[#555] text-sm">
            Você pode excluir todos os seus dados de duas formas:
          </p>
          <ul className="text-[#555] text-sm space-y-1 list-disc list-inside">
            <li>Pelo app: acesse <strong>Conexão Meta</strong> e clique em "Desconectar" para cada integração</li>
            <li>Por e-mail: envie uma solicitação para <strong>davimvf1234@gmail.com</strong></li>
            <li>
              Pelo Facebook: acesse{' '}
              <a
                href="https://www.facebook.com/settings?tab=applications"
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-400 underline"
              >
                Configurações &gt; Apps e Sites
              </a>{' '}
              e remova o adStudioAI
            </li>
          </ul>
          <p className="text-[#555] text-sm">
            Solicitações serão processadas em até 30 dias.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-semibold text-white">Contato</h2>
          <p className="text-[#555] text-sm">
            Para dúvidas ou solicitações:{' '}
            <a href="mailto:davimvf1234@gmail.com" className="text-indigo-400 underline">
              davimvf1234@gmail.com
            </a>
          </p>
        </section>
      </div>
    </div>
  )
}
