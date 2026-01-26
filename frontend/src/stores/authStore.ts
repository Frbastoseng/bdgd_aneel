import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User, Token } from '@/types'
import { authApi } from '@/services/api'

interface AuthState {
  user: User | null
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  
  // Actions
  login: (email: string, password: string) => Promise<void>
  register: (data: {
    email: string
    password: string
    full_name: string
    company?: string
    phone?: string
    message?: string
  }) => Promise<void>
  logout: () => Promise<void>
  setTokens: (accessToken: string, refreshToken: string) => void
  fetchUser: () => Promise<void>
  updateUser: (user: Partial<User>) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      
      login: async (email: string, password: string) => {
        set({ isLoading: true })
        try {
          const tokenData: Token = await authApi.login(email, password)
          
          set({
            token: tokenData.access_token,
            refreshToken: tokenData.refresh_token,
            isAuthenticated: true,
          })
          
          // Buscar dados do usuário
          await get().fetchUser()
        } finally {
          set({ isLoading: false })
        }
      },
      
      register: async (data) => {
        set({ isLoading: true })
        try {
          const user = await authApi.register(data)
          set({ user })
        } finally {
          set({ isLoading: false })
        }
      },
      
      logout: async () => {
        try {
          await authApi.logout()
        } catch {
          // Ignora erro de logout
        } finally {
          set({
            user: null,
            token: null,
            refreshToken: null,
            isAuthenticated: false,
          })
        }
      },
      
      setTokens: (accessToken: string, refreshToken: string) => {
        set({
          token: accessToken,
          refreshToken: refreshToken,
          isAuthenticated: true,
        })
      },
      
      fetchUser: async () => {
        try {
          const user = await authApi.me()
          set({ user })
        } catch {
          set({
            user: null,
            token: null,
            refreshToken: null,
            isAuthenticated: false,
          })
        }
      },
      
      updateUser: (userData: Partial<User>) => {
        const currentUser = get().user
        if (currentUser) {
          set({ user: { ...currentUser, ...userData } })
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
        user: state.user,
      }),
    }
  )
)
