import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import {
  Bars3Icon,
  XMarkIcon,
  HomeIcon,
  MagnifyingGlassIcon,
  CurrencyDollarIcon,
  MapIcon,
  UserIcon,
  Cog6ToothIcon,
  UsersIcon,
  ClipboardDocumentListIcon,
  BellIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Consulta BDGD', href: '/consulta', icon: MagnifyingGlassIcon },
  { name: 'Tarifas', href: '/tarifas', icon: CurrencyDollarIcon },
  { name: 'Mapa', href: '/mapa', icon: MapIcon },
]

const adminNavigation = [
  { name: 'Admin Dashboard', href: '/admin', icon: Cog6ToothIcon },
  { name: 'Solicitações', href: '/admin/solicitacoes', icon: ClipboardDocumentListIcon },
  { name: 'Usuários', href: '/admin/usuarios', icon: UsersIcon },
]

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  
  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }
  
  const isAdmin = user?.role === 'admin'
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-50">
      {/* Sidebar mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 lg:hidden bg-black/50 backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* Sidebar mobile */}
      <div
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-72 bg-white shadow-2xl transition-transform duration-300 lg:hidden',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-700 to-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-display font-bold text-lg">⚡</span>
            </div>
            <span className="text-lg font-display font-bold text-gray-900">BDGD</span>
          </div>
          <button 
            onClick={() => setSidebarOpen(false)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="w-6 h-6 text-gray-500" />
          </button>
        </div>
        <nav className="p-4 space-y-1 overflow-y-auto max-h-[calc(100vh-200px)]">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                isActive ? 'sidebar-link-active' : 'sidebar-link-inactive'
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          ))}
          
          {isAdmin && (
            <>
              <div className="pt-4 pb-2 px-3">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Administração
                </span>
              </div>
              {adminNavigation.map((item) => (
                <NavLink
                  key={item.name}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) =>
                    isActive ? 'sidebar-link-active' : 'sidebar-link-inactive'
                  }
                >
                  <item.icon className="w-5 h-5 flex-shrink-0" />
                  <span>{item.name}</span>
                </NavLink>
              ))}
            </>
          )}
        </nav>
      </div>
      
      {/* Sidebar desktop */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:left-0 lg:z-40 lg:w-64 lg:block">
        <div className="flex flex-col h-full bg-white border-r border-gray-100">
          <div className="flex items-center h-16 px-6 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-primary-700 to-primary-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-display font-bold text-lg">⚡</span>
              </div>
              <div>
                <span className="text-lg font-display font-bold text-gray-900">BDGD</span>
                <p className="text-xs text-gray-500">ANEEL</p>
              </div>
            </div>
          </div>
          
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) =>
                  isActive ? 'sidebar-link-active' : 'sidebar-link-inactive'
                }
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            ))}
            
            {isAdmin && (
              <>
                <div className="pt-6 pb-2 px-3">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Administração
                  </span>
                </div>
                {adminNavigation.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    className={({ isActive }) =>
                      isActive ? 'sidebar-link-active' : 'sidebar-link-inactive'
                    }
                  >
                    <item.icon className="w-5 h-5 flex-shrink-0" />
                    <span>{item.name}</span>
                  </NavLink>
                ))}
              </>
            )}
          </nav>
          
          {/* User section */}
          <div className="p-4 border-t border-gray-100 space-y-3">
            <div className="flex items-center gap-3 p-3 bg-gradient-to-r from-primary-50 to-primary-50/50 rounded-xl">
              <div className="w-10 h-10 bg-gradient-to-br from-primary-700 to-primary-600 rounded-lg flex items-center justify-center flex-shrink-0">
                <UserIcon className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">
                  {user?.full_name}
                </p>
                <p className="text-xs text-gray-500 truncate">
                  {user?.email}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <NavLink
                to="/perfil"
                className="flex-1 btn btn-outline text-xs py-2"
              >
                Perfil
              </NavLink>
              <button
                onClick={handleLogout}
                className="flex-1 btn btn-secondary text-xs py-2"
              >
                Sair
              </button>
            </div>
          </div>
        </div>
      </div>
      
      {/* Main content */}
      <div className="lg:pl-64">
        {/* Header */}
        <header className="sticky top-0 z-30 h-16 bg-white border-b border-gray-100 backdrop-blur-sm bg-white/80">
          <div className="flex items-center justify-between h-full px-4 lg:px-8">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <Bars3Icon className="w-6 h-6" />
            </button>
            
            <div className="flex-1" />
            
            <div className="flex items-center gap-4">
              <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors relative">
                <BellIcon className="w-6 h-6" />
                {isAdmin && (
                  <span className="absolute top-1 right-1 w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" />
                )}
              </button>
              
              <div className="hidden sm:flex items-center gap-3">
                <div className={clsx(
                  'badge',
                  user?.role === 'admin' ? 'badge-info' : 'badge-gray'
                )}>
                  {user?.role === 'admin' ? '👑 Admin' : '👤 Usuário'}
                </div>
              </div>

              <button
                onClick={handleLogout}
                className="lg:hidden p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                title="Sair"
              >
                <ArrowRightOnRectangleIcon className="w-6 h-6" />
              </button>
            </div>
          </div>
        </header>
        
        {/* Page content */}
        <main className="p-4 sm:p-6 lg:p-8 animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
