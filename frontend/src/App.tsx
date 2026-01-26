import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

// Layouts
import MainLayout from '@/layouts/MainLayout'
import AuthLayout from '@/layouts/AuthLayout'

// Pages
import LoginPage from '@/pages/auth/LoginPage'
import RegisterPage from '@/pages/auth/RegisterPage'
import PendingApprovalPage from '@/pages/auth/PendingApprovalPage'
import DashboardPage from '@/pages/DashboardPage'
import ConsultaPage from '@/pages/ConsultaPage'
import TarifasPage from '@/pages/TarifasPage'
import MapaPage from '@/pages/MapaPage'
import AdminPage from '@/pages/admin/AdminPage'
import AccessRequestsPage from '@/pages/admin/AccessRequestsPage'
import UsersPage from '@/pages/admin/UsersPage'
import ProfilePage from '@/pages/ProfilePage'

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
    </BrowserRouter>
  )
}

export default App
