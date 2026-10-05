export interface Account {
  id: string
  brand_name: string
  meta_page_id: string
  meta_page_name: string | null
  plan_type: string
  onboarding_step: number
  is_active: boolean
  created_at: string
}

export interface AutomationConfig {
  keyword: string
  auto_reply_message: string
  account_id: string
}

export interface MetaAuthUrl {
  auth_url: string
}

export interface MetaCallbackResponse {
  success: boolean
  account_id: string
  brand_name: string
  page_name: string | null
  onboarding_step: number
}

export interface OnboardingStatus {
  account_id: string
  brand_name: string
  page_name: string | null
  plan_type: string
  onboarding_step: number
  instagram_connected: boolean
  ad_account_selected: boolean
}

export interface AdAccount {
  id: string
  name: string
  account_status: number
  currency: string
}

export interface PerformancePoint {
  date: string
  impressions: number
  clicks: number
  conversions: number
}

export interface RecentActivity {
  id: string
  type: string
  description: string
  created_at: string
}

export interface AlertItem {
  id: string
  type: string
  severity: string
  title: string
  description: string | null
  created_at: string
}

export interface Lead {
  id: string
  account_id: string
  name: string | null
  instagram_handle: string
  ig_user_id: string | null
  email: string | null
  phone: string | null
  source: string
  status: string
  score: number | null
  score_label: string | null
  score_notes: string | null
  last_scored_at: string | null
  captured_at: string
  created_at: string
}

export interface AgencyClientStat {
  id: string
  brand_name: string
  is_active: boolean
  leads: number
  converted: number
  conversion_rate: number
  new_leads_7d: number
  instagram_connected: boolean
}

export interface AgencyDashboard {
  total_clients: number
  active_clients: number
  total_leads: number
  total_converted: number
  overall_conversion_rate: number
  new_leads_7d: number
  clients: AgencyClientStat[]
}

export interface DashboardData {
  total_leads: number
  total_customers: number
  new_customers_30d: number
  conversion_rate: number
  total_revenue: number
  monthly_revenue: number
  average_ticket: number
  projected_revenue: number
  ads_spent: number
  ads_impressions: number
  ads_clicks: number
  ads_ctr: number
  ads_cpm: number
  ads_roas: number
  instagram_posts: number
  instagram_reach: number
  instagram_engagement: number
  instagram_followers_delta: number
  videos_generated_month: number
  credits_total: number
  credits_used: number
  last_video_title: string | null
  last_video_created_at: string | null
  performance: PerformancePoint[]
  recent_activity: RecentActivity[]
  alerts: AlertItem[]
}
