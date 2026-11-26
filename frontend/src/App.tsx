import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'

// Cada tela carrega só quando é aberta (o celular baixa bem menos na entrada).
const Instalar = lazy(() => import('./pages/Instalar'))
const Onboarding = lazy(() => import('./pages/Onboarding'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const ConexaoMeta = lazy(() => import('./pages/ConexaoMeta'))
const Leads = lazy(() => import('./pages/Leads'))
const Configuracoes = lazy(() => import('./pages/Configuracoes'))
const PublicarInstagram = lazy(() => import('./pages/PublicarInstagram'))
const AIConfig = lazy(() => import('./pages/AIConfig'))
const Privacy = lazy(() => import('./pages/Privacy'))
const Terms = lazy(() => import('./pages/Terms'))
const DataDeletion = lazy(() => import('./pages/DataDeletion'))
const Guide = lazy(() => import('./pages/Guide'))
const PublicGuide = lazy(() => import('./pages/Guide').then((m) => ({ default: m.PublicGuide })))
const Pricing = lazy(() => import('./pages/Pricing'))
const CompletarCadastro = lazy(() => import('./pages/CompletarCadastro'))
const Clients = lazy(() => import('./pages/Clients'))
const Marketing = lazy(() => import('./pages/Marketing'))
const MarketingCampaignDetail = lazy(() => import('./pages/MarketingCampaignDetail'))
const WhatsApp = lazy(() => import('./pages/WhatsApp'))
const InstagramInbox = lazy(() => import('./pages/InstagramInbox'))
const Templates = lazy(() => import('./pages/Templates'))
const Equipe = lazy(() => import('./pages/Equipe'))
const SuperAdmin = lazy(() => import('./pages/SuperAdmin'))
const FollowUps = lazy(() => import('./pages/FollowUps'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))
const ResetPassword = lazy(() => import('./pages/ResetPassword'))
const VerifyEmail = lazy(() => import('./pages/VerifyEmail'))
const OAuthSuccess = lazy(() => import('./pages/OAuthSuccess'))

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="min-h-screen bg-canvas" />}>
      <Routes>
        <Route path="/oauth/success" element={<OAuthSuccess />} />
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/instalar" element={<Instalar />} />
        <Route path="/download" element={<Instalar />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/data-deletion" element={<DataDeletion />} />
        <Route path="/guia" element={<PublicGuide />} />
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
          <Route path="/app/guia" element={<Guide />} />
          <Route path="/app/planos" element={<Pricing embedded />} />
          <Route path="/app/clientes" element={<Clients />} />
          <Route path="/app/super-admin" element={<SuperAdmin />} />
          <Route path="/app/marketing" element={<Marketing />} />
          <Route path="/app/marketing/:campaignId" element={<MarketingCampaignDetail />} />
        </Route>
      </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
