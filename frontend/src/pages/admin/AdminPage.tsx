import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { adminApi } from '@/services/api'
import type { AdminStats } from '@/types'
import {
  UsersIcon,
  ClipboardDocumentListIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline'

export default function AdminPage() {
  const { data: stats, isLoading } = useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: adminApi.stats,
  })
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="spinner w-8 h-8 text-primary-600" />
      </div>
    )
  }
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Painel Administrativo</h1>
        <p className="text-gray-600">
          Gerencie usuários e solicitações de acesso
        </p>
      </div>
      
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <UsersIcon className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {stats?.total_users || 0}
              </p>
              <p className="text-sm text-gray-600">Total de Usuários</p>
            </div>
          </div>
        </div>
        
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <ClipboardDocumentListIcon className="w-6 h-6 text-yellow-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {stats?.pending_requests || 0}
              </p>
              <p className="text-sm text-gray-600">Solicitações Pendentes</p>
            </div>
          </div>
        </div>
        
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <ShieldCheckIcon className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {stats?.active_users || 0}
              </p>
              <p className="text-sm text-gray-600">Usuários Ativos</p>
            </div>
          </div>
        </div>
        
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <ChartBarIcon className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {stats?.total_queries_today || 0}
              </p>
              <p className="text-sm text-gray-600">Consultas Hoje</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link to="/admin/solicitacoes" className="card p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
                <ClipboardDocumentListIcon className="w-6 h-6 text-yellow-600" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Solicitações de Acesso</h3>
                <p className="text-sm text-gray-600">
                  {stats?.pending_requests || 0} pendentes para revisão
                </p>
              </div>
            </div>
            <ArrowRightIcon className="w-5 h-5 text-gray-400" />
          </div>
          {stats?.pending_requests && stats.pending_requests > 0 && (
            <div className="mt-4 p-3 bg-yellow-50 rounded-lg">
              <p className="text-sm text-yellow-700">
                ⚠️ Há {stats.pending_requests} solicitações aguardando sua análise
              </p>
            </div>
          )}
        </Link>
        
        <Link to="/admin/usuarios" className="card p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <UsersIcon className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Gerenciar Usuários</h3>
                <p className="text-sm text-gray-600">
                  {stats?.total_users || 0} usuários cadastrados
                </p>
              </div>
            </div>
            <ArrowRightIcon className="w-5 h-5 text-gray-400" />
          </div>
        </Link>
      </div>
    </div>
  )
}
