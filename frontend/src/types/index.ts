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

// Tipos para Mapa Avançado
export interface PontoMapaCompleto {
  id: string
  latitude: number
  longitude: number
  cod_id?: string
  titulo?: string
  tipo_consumidor: string  // "livre" ou "cativo"
  classe?: string
  grupo_tarifario?: string
  municipio?: string
  uf?: string
  demanda?: number
  demanda_contratada?: number
  consumo_medio?: number
  consumo_max?: number
  carga_instalada?: number
  possui_solar: boolean
  cluster_id?: number
}

export interface MapaAvancadoResponse {
  pontos: PontoMapaCompleto[]
  total: number
  centro: { lat: number; lng: number }
  zoom: number
  estatisticas?: {
    total_pontos: number
    total_base: number
    com_solar: number
    livres: number
    cativos: number
    demanda_media?: number
  }
}

export interface AreaSelecao {
  north: number
  south: number
  east: number
  west: number
}

// Tipos para Consultas Salvas
export interface ConsultaSalva {
  id: number
  name: string
  description?: string
  filters: Record<string, unknown>
  query_type: 'consulta' | 'mapa' | 'tarifas'
  created_at: string
  updated_at?: string
  last_used_at?: string
  use_count: number
}

export interface CriarConsultaSalva {
  name: string
  description?: string
  filters: Record<string, unknown>
  query_type?: 'consulta' | 'mapa' | 'tarifas'
}

// Tipos CNPJ
export interface SocioInfo {
  nome: string
  qualificacao: string
}

export interface SocioDetailInfo {
  nome: string
  qualificacao: string
  codigo_qualificacao?: number | null
  cnpj_cpf?: string | null
  data_entrada_sociedade?: string | null
  faixa_etaria?: string | null
  identificador_de_socio?: number | null
  pais?: string | null
  nome_representante_legal?: string | null
  qualificacao_representante_legal?: string | null
}

export interface CnaeSecundario {
  codigo?: number | string | null
  descricao?: string | null
}

export interface RegimeTributario {
  ano?: number | null
  forma_de_tributacao?: string | null
  quantidade_de_escrituracoes?: number | null
}

export interface CnpjCacheItem {
  id: number
  cnpj: string
  razao_social?: string | null
  nome_fantasia?: string | null
  situacao_cadastral?: string | null
  cnae_fiscal_descricao?: string | null
  municipio?: string | null
  uf?: string | null
  telefone_1?: string | null
  email?: string | null
  capital_social?: number | null
  porte?: string | null
  natureza_juridica?: string | null
  data_inicio_atividade?: string | null
  opcao_pelo_simples?: string | null
  opcao_pelo_mei?: string | null
  socios?: SocioInfo[] | null
  data_consulta?: string | null
  updated_at?: string | null
  logradouro?: string | null
  numero?: string | null
  complemento?: string | null
  bairro?: string | null
  cep?: string | null
}

export interface CnpjCacheDetail extends CnpjCacheItem {
  telefone_2?: string | null
  cnaes_secundarios?: CnaeSecundario[] | null
  cnae_fiscal?: string | null
  data_situacao_cadastral?: string | null
  motivo_situacao_cadastral?: string | null
  descricao_tipo_logradouro?: string | null
  identificador_matriz_filial?: string | null
  data_opcao_pelo_simples?: string | null
  data_exclusao_do_simples?: string | null
  situacao_especial?: string | null
  data_situacao_especial?: string | null
  nome_cidade_exterior?: string | null
  pais?: string | null
  regime_tributario?: RegimeTributario[] | null
  socios_detalhados?: SocioDetailInfo[] | null
  data_consulta_formatada?: string | null
}

export interface CnpjCachePaginated {
  data: CnpjCacheItem[]
  total: number
  page: number
  per_page: number
}

export interface CnpjCacheStats {
  total: number
  ativas: number
}

export interface CnpjSearchItem {
  cnpj: string
  razao_social?: string | null
  nome_fantasia?: string | null
  municipio?: string | null
  uf?: string | null
  situacao_cadastral?: string | null
}

// Tipos Matching BDGD-CNPJ
export interface MatchItem {
  cnpj: string
  rank: number
  score_total: number
  score_cep: number
  score_cnae: number
  score_endereco: number
  score_numero: number
  score_bairro: number
  razao_social?: string | null
  nome_fantasia?: string | null
  cnpj_logradouro?: string | null
  cnpj_numero?: string | null
  cnpj_bairro?: string | null
  cnpj_cep?: string | null
  cnpj_municipio?: string | null
  cnpj_uf?: string | null
  cnpj_cnae?: string | null
  cnpj_cnae_descricao?: string | null
  cnpj_situacao?: string | null
  cnpj_telefone?: string | null
  cnpj_email?: string | null
}

export interface BdgdClienteComMatch {
  cod_id: string
  lgrd_original?: string | null
  brr_original?: string | null
  cep_original?: string | null
  cnae_original?: string | null
  municipio_nome?: string | null
  uf?: string | null
  clas_sub?: string | null
  gru_tar?: string | null
  dem_cont?: number | null
  ene_max?: number | null
  liv?: number | null
  possui_solar?: boolean
  point_x?: number | null
  point_y?: number | null
  matches: MatchItem[]
  best_score?: number | null
}

export interface MatchingPaginated {
  data: BdgdClienteComMatch[]
  total: number
  page: number
  per_page: number
}

export interface MatchingStats {
  total_clientes: number
  clientes_com_match: number
  clientes_sem_match: number
  avg_score_top1?: number | null
  alta_confianca: number
  media_confianca: number
  baixa_confianca: number
  total_matches: number
}
