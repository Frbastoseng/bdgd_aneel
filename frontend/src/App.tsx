import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import { useAuthStore } from '@/stores/authStore'

// Layouts (carregados imediatamente)
import MainLayout from '@/layouts/MainLayout'
import AuthLayout from '@/layouts/AuthLayout'

// Loading component
const PageLoader = () => (
  <div className="min-h-screen flex items-center justify-center bg-gray-50">
    <div className="text-center">
      <div className="w-16 h-16 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-4"></div>
      <p className="text-gray-600 font-medium">Carregando...</p>
    </div>
  </div>
)

// Pages - Lazy Loading para carregar apenas quando necessário
const LoginPage = lazy(() => import('@/pages/auth/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage'))
const PendingApprovalPage = lazy(() => import('@/pages/auth/PendingApprovalPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const ConsultaPage = lazy(() => import('@/pages/ConsultaPage'))
const TarifasPage = lazy(() => import('@/pages/TarifasPage'))
const MapaPage = lazy(() => import('@/pages/MapaPage'))
const AdminPage = lazy(() => import('@/pages/admin/AdminPage'))
const AccessRequestsPage = lazy(() => import('@/pages/admin/AccessRequestsPage'))
const UsersPage = lazy(() => import('@/pages/admin/UsersPage'))
const ProfilePage = lazy(() => import('@/pages/ProfilePage'))
const CnpjPage = lazy(() => import('@/pages/CnpjPage'))
const MatchingPage = lazy(() => import('@/pages/MatchingPage'))

// Protected Route Component
function ProtectedRoute({ children, requireAdmin = false }: { children: React.ReactNode; requireAdmin?: boolean }) {
  const { isAuthenticated, user } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  if (user?.status === 'pending') {
    return <Navigate to="/pending-approval" replace />
  }
  
  if (user?.status !== 'approved') {
    return <Navigate to="/login" replace />
  }
  
  if (requireAdmin && user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }
  
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Auth Routes */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/pending-approval" element={<PendingApprovalPage />} />
          </Route>
          
          {/* Protected Routes */}
          <Route element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/consulta" element={<ConsultaPage />} />
            <Route path="/tarifas" element={<TarifasPage />} />
            <Route path="/mapa" element={<MapaPage />} />
            <Route path="/cnpj" element={<CnpjPage />} />
            <Route path="/matching" element={<MatchingPage />} />
            <Route path="/perfil" element={<ProfilePage />} />
          </Route>
          
          {/* Admin Routes */}
          <Route element={
            <ProtectedRoute requireAdmin>
              <MainLayout />
            </ProtectedRoute>
          }>
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/admin/solicitacoes" element={<AccessRequestsPage />} />
            <Route path="/admin/usuarios" element={<UsersPage />} />
          </Route>
          
          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
