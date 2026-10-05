export default function Configuracoes() {
  return (
    <div>
      <h2 className="text-2xl font-bold text-[#e2e2e8] mb-6">Configurações</h2>
      <div className="bg-[#111118] rounded-xl border border-white/[0.06] p-8 max-w-lg space-y-6">
        <div>
          <label className="block text-sm font-medium text-[#666] mb-1">Nome da Marca</label>
          <input type="text" placeholder="Minha Marca" className="w-full px-4 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none placeholder-[#333]" />
        </div>
        <div>
          <label className="block text-sm font-medium text-[#666] mb-1">Idioma</label>
          <select className="w-full px-4 py-2 bg-[#0a0a0f] border border-white/[0.08] text-[#e2e2e8] rounded-lg focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-none">
            <option>Português (Brasil)</option>
            <option>English (US)</option>
            <option>Español</option>
          </select>
        </div>
        <div className="pt-4 border-t border-white/[0.06]">
          <h4 className="text-sm font-medium text-[#555] mb-2">Informações do Sistema</h4>
          <p className="text-xs text-[#444]">Versão: 1.0.0</p>
          <p className="text-xs text-[#444]">Ambiente: Desenvolvimento</p>
        </div>
      </div>
    </div>
  )
}
