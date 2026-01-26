import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { aneelApi, adminApi } from '@/services/api'
import {
  ChartBarIcon,
  UsersIcon,
  ClipboardDocumentListIcon,
  BoltIcon,
  SunIcon,
  MapPinIcon,
} from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'
  
  const { data: statusDados } = useQuery({
    queryKey: ['status-dados'],
    queryFn: aneelApi.statusDados,
  })
  
  const { data: adminStats } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: adminApi.stats,
    enabled: isAdmin,
  })
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Bem-vindo, {user?.full_name?.split(' ')[0]}!
        </h1>
        <p className="text-gray-600 mt-1">
          Sistema de Consulta de Dados da ANEEL (BDGD)
        </p>
      </div>
      
      {/* Admin Stats */}
      {isAdmin && adminStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="card p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <UsersIcon className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {adminStats.total_users}
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
                  {adminStats.pending_requests}
                </p>
                <p className="text-sm text-gray-600">Solicitações Pendentes</p>
              </div>
            </div>
            {adminStats.pending_requests > 0 && (
              <Link
                to="/admin/solicitacoes"
                className="mt-4 text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                Ver solicitações →
              </Link>
            )}
          </div>
          
          <div className="card p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <UsersIcon className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {adminStats.active_users}
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
                  {adminStats.total_queries_today}
                </p>
                <p className="text-sm text-gray-600">Consultas Hoje</p>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Status dos Dados */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900">
            Status dos Dados ANEEL
          </h2>
        </div>
        <div className="card-body">
          {statusDados?.disponivel ? (
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <BoltIcon className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <p className="text-lg font-medium text-gray-900">
                  Dados Disponíveis
                </p>
                <p className="text-sm text-gray-600">
                  {statusDados.total_registros?.toLocaleString('pt-BR')} registros
                  {statusDados.ultima_atualizacao && (
                    <> • Última atualização: {new Date(statusDados.ultima_atualizacao).toLocaleString('pt-BR')}</>
                  )}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
                <BoltIcon className="w-6 h-6 text-yellow-600" />
              </div>
              <div>
                <p className="text-lg font-medium text-gray-900">
                  Dados Não Disponíveis
                </p>
                <p className="text-sm text-gray-600">
                  Clique em "Atualizar Dados" para baixar
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Acesso Rápido
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Link to="/consulta" className="card p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center">
                <BoltIcon className="w-6 h-6 text-primary-600" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Consulta BDGD</h3>
                <p className="text-sm text-gray-600">
                  Pesquisar dados de clientes
                </p>
              </div>
            </div>
          </Link>
          
          <Link to="/tarifas" className="card p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <SunIcon className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Tarifas</h3>
                <p className="text-sm text-gray-600">
                  Consultar tarifas de energia
                </p>
              </div>
            </div>
          </Link>
          
          <Link to="/mapa" className="card p-6 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <MapPinIcon className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Mapa</h3>
                <p className="text-sm text-gray-600">
                  Visualizar no mapa com Street View
                </p>
              </div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  )
}
