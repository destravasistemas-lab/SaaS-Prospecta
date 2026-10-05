import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import ConexaoMeta from './pages/ConexaoMeta'
import Leads from './pages/Leads'
import Configuracoes from './pages/Configuracoes'
import PublicarInstagram from './pages/PublicarInstagram'
import AIConfig from './pages/AIConfig'
import Privacy from './pages/Privacy'
import Pricing from './pages/Pricing'
import CompletarCadastro from './pages/CompletarCadastro'
import Clients from './pages/Clients'
import Marketing from './pages/Marketing'
import MarketingCampaignDetail from './pages/MarketingCampaignDetail'
import WhatsApp from './pages/WhatsApp'
import InstagramInbox from './pages/InstagramInbox'
import Templates from './pages/Templates'
import Equipe from './pages/Equipe'
import SuperAdmin from './pages/SuperAdmin'
import FollowUps from './pages/FollowUps'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import VerifyEmail from './pages/VerifyEmail'
import OAuthSuccess from './pages/OAuthSuccess'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/oauth/success" element={<OAuthSuccess />} />
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/completar-cadastro" element={<CompletarCadastro />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route element={<Layout />}>
          <Route path="/app" element={<Dashboard />} />
          <Route path="/app/conexao" element={<ConexaoMeta />} />
          <Route path="/app/publicar" element={<PublicarInstagram />} />
          {/* Publicar + Automação foram unificados em /app/publicar */}
          <Route path="/app/automacao" element={<Navigate to="/app/publicar" replace />} />
          <Route path="/app/whatsapp" element={<WhatsApp />} />
          <Route path="/app/ia" element={<AIConfig />} />
          <Route path="/app/instagram-dm" element={<InstagramInbox />} />
          <Route path="/app/templates" element={<Templates />} />
          <Route path="/app/equipe" element={<Equipe />} />
          <Route path="/app/followups" element={<FollowUps />} />
          <Route path="/app/leads" element={<Leads />} />
          <Route path="/app/configuracoes" element={<Configuracoes />} />
          <Route path="/app/clientes" element={<Clients />} />
          <Route path="/app/super-admin" element={<SuperAdmin />} />
          <Route path="/app/marketing" element={<Marketing />} />
          <Route path="/app/marketing/:campaignId" element={<MarketingCampaignDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
