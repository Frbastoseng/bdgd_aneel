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

// Interceptor para tratar erros
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    
    // Se token expirou, tenta refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      
      const refreshToken = useAuthStore.getState().refreshToken
      
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          
          const { access_token, refresh_token } = response.data
          useAuthStore.getState().setTokens(access_token, refresh_token)
          
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return api(originalRequest)
        } catch (refreshError) {
          useAuthStore.getState().logout()
          window.location.href = '/login'
          return Promise.reject(refreshError)
        }
      }
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
  
  statusDados: async () => {
    const response = await api.get('/aneel/status-dados')
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
