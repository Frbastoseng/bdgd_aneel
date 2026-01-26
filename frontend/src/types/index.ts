// Tipos de usuário
export type UserStatus = 'pending' | 'approved' | 'rejected' | 'suspended'
export type UserRole = 'admin' | 'user' | 'viewer'

export interface User {
  id: number
  email: string
  full_name: string
  company?: string
  phone?: string
  role: UserRole
  status: UserStatus
  is_active: boolean
  created_at: string
  updated_at?: string
  last_login?: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  company?: string
  phone?: string
  message?: string
}

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface AccessRequest {
  id: number
  user_id: number
  user_email: string
  user_name: string
  message?: string
  status: UserStatus
  admin_response?: string
  created_at: string
  reviewed_at?: string
}

// Tipos ANEEL
export interface FiltroConsulta {
  [key: string]: unknown
  uf?: string
  municipios?: string[]
  microrregioes?: string[]
  mesorregioes?: string[]
  possui_solar?: boolean
  classes_cliente?: string[]
  grupos_tarifarios?: string[]
  tipo_consumidor?: string
  demanda_min?: number
  demanda_max?: number
  energia_max_min?: number
  energia_max_max?: number
  page?: number
  per_page?: number
}

export interface ClienteANEEL {
  id?: number
  cod_id?: string
  mun?: string
  nome_uf?: string
  nome_municipio?: string
  clas_sub?: string
  clas_sub_descricao?: string
  gru_tar?: string
  liv?: number
  dem_cont?: number
  car_inst?: number
  ene_max?: number
  ceg_gd?: string
  possui_solar?: boolean
  point_x?: number
  point_y?: number
  latitude?: number
  longitude?: number
}

export interface ConsultaResponse {
  dados: ClienteANEEL[]
  total: number
  page: number
  per_page: number
  total_pages: number
  estatisticas?: Record<string, unknown>
}

export interface PontoMapa {
  id: string
  latitude: number
  longitude: number
  titulo: string
  descricao?: string
  tipo?: string
  dados?: Record<string, unknown>
}

export interface MapaResponse {
  pontos: PontoMapa[]
  centro: { lat: number; lng: number }
  zoom: number
}

export interface TarifaANEEL {
  id?: number
  sig_agente?: string
  dsc_reh?: string
  nom_posto_tarifario?: string
  dsc_unidade_terciaria?: string
  vlr_tusd?: number
  vlr_te?: number
  dat_fim_vigencia?: string
  dsc_sub_grupo?: string
  dsc_modalidade_tarifaria?: string
  dsc_detalhe?: string
}

export interface FiltroTarifas {
  [key: string]: unknown
  distribuidora?: string
  subgrupo?: string
  modalidade?: string
  detalhe?: string
  apenas_ultima_tarifa?: boolean
}

export interface TarifasResponse {
  tarifas: TarifaANEEL[]
  total: number
}

export interface AdminStats {
  total_users: number
  pending_requests: number
  active_users: number
  total_queries_today: number
}

export interface OpcoesFiltros {
  ufs?: string[]
  municipios?: string[]
  microrregioes?: string[]
  mesorregioes?: string[]
  municipios_por_uf?: Record<string, string[]>
  microrregioes_por_uf?: Record<string, string[]>
  mesorregioes_por_uf?: Record<string, string[]>
  grupos_tarifarios: string[]
  classes_cliente: string[]
  tipos_consumidor: string[]
}

export interface OpcoesFiltrosTarifas {
  distribuidoras: string[]
  subgrupos: string[]
  modalidades: string[]
  detalhes: string[]
}
