import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Interceptor para adicionar token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Flag para evitar múltiplos refreshes simultâneos
let isRefreshing = false
let refreshSubscribers: ((token: string) => void)[] = []

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}

function onRefreshed(token: string) {
  refreshSubscribers.forEach(cb => cb(token))
  refreshSubscribers = []
}

// Interceptor para tratar erros
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    
    // URLs que não devem tentar refresh
    const noRefreshUrls = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']
    const isAuthUrl = noRefreshUrls.some(url => originalRequest?.url?.includes(url))
    
    // Se token expirou e não é uma URL de auth
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthUrl) {
      originalRequest._retry = true
      
      const refreshToken = useAuthStore.getState().refreshToken
      
      if (refreshToken && !isRefreshing) {
        isRefreshing = true
        
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          
          const { access_token, refresh_token } = response.data
          useAuthStore.getState().setTokens(access_token, refresh_token)
          
          isRefreshing = false
          onRefreshed(access_token)
          
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        } catch (refreshError) {
          isRefreshing = false
          refreshSubscribers = []
          
          // Limpar estado e parar o loop
          useAuthStore.setState({
            user: null,
            token: null,
            refreshToken: null,
            isAuthenticated: false,
          })
          
          // Só redireciona se não estiver já na página de login
          if (!window.location.pathname.includes('/login')) {
            window.location.href = '/login'
          }
          return Promise.reject(refreshError)
        }
      } else if (isRefreshing) {
        // Se já está fazendo refresh, aguarda o token novo
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(api(originalRequest))
          })
        })
      }
    }
    
    // Se é 401 em URLs de auth, apenas limpa o estado sem redirecionar
    if (error.response?.status === 401 && isAuthUrl) {
      useAuthStore.setState({
        user: null,
        token: null,
        refreshToken: null,
        isAuthenticated: false,
      })
    }
    
    return Promise.reject(error)
  }
)

// API de Autenticação
export const authApi = {
  login: async (email: string, password: string) => {
    const response = await api.post('/auth/login', { email, password })
    return response.data
  },
  
  register: async (data: {
    email: string
    password: string
    full_name: string
    company?: string
    phone?: string
    message?: string
  }) => {
    const response = await api.post('/auth/register', data)
    return response.data
  },
  
  refresh: async (refreshToken: string) => {
    const response = await api.post('/auth/refresh', { refresh_token: refreshToken })
    return response.data
  },
  
  logout: async () => {
    const response = await api.post('/auth/logout')
    return response.data
  },
  
  me: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },
}

// API ANEEL
export const aneelApi = {
  consulta: async (filtros: Record<string, unknown>) => {
    const response = await api.post('/aneel/consulta', filtros)
    return response.data
  },
  
  mapa: async (params: Record<string, unknown>) => {
    const response = await api.get('/aneel/mapa', { params })
    return response.data
  },
  
  // Mapa avançado com pontos completos
  mapaAvancado: async (params: Record<string, unknown>) => {
    const response = await api.get('/aneel/mapa/pontos', { params })
    return response.data
  },
  
  // Exportar seleção do mapa
  exportarSelecaoMapa: async (data: {
    bounds: { north: number; south: number; east: number; west: number };
    filtros?: Record<string, unknown>;
    formato?: 'xlsx' | 'csv';
  }) => {
    const response = await api.post('/aneel/mapa/exportar-selecao', data, {
      responseType: 'blob',
    })
    return response.data
  },
  
  opcoesFiltros: async () => {
    const response = await api.get('/aneel/opcoes-filtros')
    return response.data
  },
  
  exportarCsv: async (filtros: Record<string, unknown>) => {
    const response = await api.post('/aneel/exportar/csv', filtros, {
      responseType: 'blob',
    })
    return response.data
  },
  
  exportarXlsx: async (filtros: Record<string, unknown>) => {
    const response = await api.post('/aneel/exportar/xlsx', filtros, {
      responseType: 'blob',
    })
    return response.data
  },
  
  exportarKml: async (filtros: Record<string, unknown>) => {
    const response = await api.post('/aneel/exportar/kml', filtros, {
      responseType: 'blob',
    })
    return response.data
  },
  
  atualizarDados: async () => {
    const response = await api.post('/aneel/atualizar-dados')
    return response.data
  },
  
  progressoDownload: async () => {
    const response = await api.get('/aneel/progresso-download')
    return response.data
  },
  
  statusDados: async () => {
    const response = await api.get('/aneel/status-dados')
    return response.data
  },
  
  // Consultas Salvas
  listarConsultasSalvas: async (queryType?: string) => {
    const params = queryType ? { query_type: queryType } : {}
    const response = await api.get('/aneel/consultas-salvas', { params })
    return response.data
  },
  
  salvarConsulta: async (data: {
    name: string;
    description?: string;
    filters: Record<string, unknown>;
    query_type?: string;
  }) => {
    const response = await api.post('/aneel/consultas-salvas', data)
    return response.data
  },
  
  atualizarConsultaSalva: async (id: number, data: {
    name?: string;
    description?: string;
    filters?: Record<string, unknown>;
  }) => {
    const response = await api.put(`/aneel/consultas-salvas/${id}`, data)
    return response.data
  },
  
  excluirConsultaSalva: async (id: number) => {
    const response = await api.delete(`/aneel/consultas-salvas/${id}`)
    return response.data
  },
  
  usarConsultaSalva: async (id: number) => {
    const response = await api.post(`/aneel/consultas-salvas/${id}/usar`)
    return response.data
  },
  
  // Tarifas
  consultaTarifas: async (filtros: Record<string, unknown>) => {
    const response = await api.post('/aneel/tarifas/consulta', filtros)
    return response.data
  },
  
  opcoesFiltrosTarifas: async () => {
    const response = await api.get('/aneel/tarifas/opcoes-filtros')
    return response.data
  },
  
  atualizarTarifas: async () => {
    const response = await api.post('/aneel/tarifas/atualizar')
    return response.data
  },
}

// API Admin
export const adminApi = {
  stats: async () => {
    const response = await api.get('/admin/stats')
    return response.data
  },
  
  users: async (page = 1, perPage = 20, status?: string) => {
    const params: Record<string, unknown> = { page, per_page: perPage }
    if (status) params.status = status
    const response = await api.get('/admin/users', { params })
    return response.data
  },
  
  getUser: async (userId: number) => {
    const response = await api.get(`/admin/users/${userId}`)
    return response.data
  },
  
  updateUser: async (userId: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/admin/users/${userId}`, data)
    return response.data
  },
  
  accessRequests: async (page = 1, perPage = 20) => {
    const response = await api.get('/admin/access-requests', {
      params: { page, per_page: perPage },
    })
    return response.data
  },
  
  reviewRequest: async (requestId: number, status: string, adminResponse?: string) => {
    const response = await api.post(`/admin/access-requests/${requestId}/review`, {
      status,
      admin_response: adminResponse,
    })
    return response.data
  },
  
  suspendUser: async (userId: number) => {
    const response = await api.post(`/admin/users/${userId}/suspend`)
    return response.data
  },
  
  activateUser: async (userId: number) => {
    const response = await api.post(`/admin/users/${userId}/activate`)
    return response.data
  },
}

export default api
