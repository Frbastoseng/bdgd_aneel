import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

export default function AuthLayout() {
  const { isAuthenticated, user } = useAuthStore()
  const location = useLocation()
  
  // Se já está autenticado, redireciona conforme o status
  if (isAuthenticated && user) {
    if (user.status === 'pending' && location.pathname !== '/pending-approval') {
      return <Navigate to="/pending-approval" replace />
    }
    if (user.status === 'approved') {
      return <Navigate to="/" replace />
    }
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-600 via-primary-700 to-primary-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Outlet />
      </div>
    </div>
  )
}
