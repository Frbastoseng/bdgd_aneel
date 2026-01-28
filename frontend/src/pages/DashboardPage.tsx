import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { aneelApi, adminApi } from '@/services/api'
import { toast } from 'react-hot-toast'
import { useState, useEffect } from 'react'
import {
  ChartBarIcon,
  UsersIcon,
  ClipboardDocumentListIcon,
  BoltIcon,
  SunIcon,
  MapPinIcon,
  ArrowTrendingUpIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom'

// Tipos para o progresso
interface DownloadProgress {
  status: 'idle' | 'downloading' | 'completed' | 'error'
  current: number
  total: number
  percent: number
  message: string
  started_at: string | null
  completed_at: string | null
  error: string | null
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'
  const queryClient = useQueryClient()
  const [isPolling, setIsPolling] = useState(false)
  
  const { data: statusDados, refetch: refetchStatus } = useQuery({
    queryKey: ['status-dados'],
    queryFn: aneelApi.statusDados,
  })
  
  const { data: adminStats } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: adminApi.stats,
    enabled: isAdmin,
  })
  
  // Query para progresso do download - apenas quando polling ativo
  const { data: progressoDownload } = useQuery<DownloadProgress>({
    queryKey: ['progresso-download'],
    queryFn: aneelApi.progressoDownload,
    enabled: isAdmin && isPolling,
    refetchInterval: isPolling ? 2000 : false, // Poll a cada 2 segundos
  })
  
  // Efeito para controlar o polling baseado no status
  useEffect(() => {
    if (progressoDownload) {
      if (progressoDownload.status === 'downloading') {
        setIsPolling(true)
      } else if (progressoDownload.status === 'completed') {
        setIsPolling(false)
        refetchStatus()
        toast.success('Download concluído com sucesso!')
      } else if (progressoDownload.status === 'error') {
        setIsPolling(false)
        toast.error(`Erro no download: ${progressoDownload.error}`)
      }
    }
  }, [progressoDownload, refetchStatus])
  
  // Mutation para atualizar dados - apenas admin
  const atualizarDadosMutation = useMutation({
    mutationFn: aneelApi.atualizarDados,
    onSuccess: () => {
      toast.success('Atualização iniciada!')
      setIsPolling(true)
      queryClient.invalidateQueries({ queryKey: ['progresso-download'] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Erro ao iniciar atualização')
    }
  })
  
  return (
    <div className="space-y-8">
      {/* Header Section */}
      <div className="animate-slide-up">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-display font-bold text-gray-900 dark:text-white">
              Bem-vindo, {user?.full_name?.split(' ')[0]}! 👋
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-2 text-lg">
              Sistema de Consulta de Dados da ANEEL (BDGD)
            </p>
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {new Date().toLocaleDateString('pt-BR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </div>
        </div>
      </div>
      
      {/* Admin Stats */}
      {isAdmin && adminStats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-slide-up">
          {/* Total Users */}
          <div className="stat-card group">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Total de Usuários</p>
                <p className="text-3xl font-display font-bold text-gray-900 dark:text-white">
                  {adminStats.total_users}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">Cadastrados no sistema</p>
              </div>
              <div className="stat-icon bg-gradient-to-br from-blue-100 to-blue-50 group-hover:scale-110 transition-transform">
                <UsersIcon className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>
          
          {/* Pending Requests */}
          <div className="stat-card group">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Solicitações Pendentes</p>
                <p className="text-3xl font-display font-bold text-gray-900 dark:text-white">
                  {adminStats.pending_requests}
                </p>
                {adminStats.pending_requests > 0 && (
                  <Link
                    to="/admin/solicitacoes"
                    className="text-xs text-primary-600 hover:text-primary-700 font-semibold mt-2 inline-block"
                  >
                    Ver solicitações →
                  </Link>
                )}
              </div>
              <div className="stat-icon bg-gradient-to-br from-yellow-100 to-yellow-50 group-hover:scale-110 transition-transform">
                <ClipboardDocumentListIcon className="w-6 h-6 text-yellow-600" />
              </div>
            </div>
          </div>
          
          {/* Active Users */}
          <div className="stat-card group">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Usuários Ativos</p>
                <p className="text-3xl font-display font-bold text-gray-900 dark:text-white">
                  {adminStats.active_users}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">Últimos 30 dias</p>
              </div>
              <div className="stat-icon bg-gradient-to-br from-green-100 to-green-50 group-hover:scale-110 transition-transform">
                <ArrowTrendingUpIcon className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>
          
          {/* Queries Today */}
          <div className="stat-card group">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Consultas Hoje</p>
                <p className="text-3xl font-display font-bold text-gray-900 dark:text-white">
                  {adminStats.total_queries_today}
                </p>
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">Requisições processadas</p>
              </div>
              <div className="stat-icon bg-gradient-to-br from-purple-100 to-purple-50 group-hover:scale-110 transition-transform">
                <ChartBarIcon className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Status dos Dados */}
      <div className="card animate-slide-up">
        <div className="card-header">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-display font-bold text-gray-900 dark:text-white">
              Status dos Dados ANEEL
            </h2>
            <div className="flex items-center gap-4">
              {/* Botão Atualizar - apenas admin */}
              {isAdmin && progressoDownload?.status !== 'downloading' && (
                <button
                  onClick={() => atualizarDadosMutation.mutate()}
                  disabled={atualizarDadosMutation.isPending}
                  className="btn-primary flex items-center gap-2 text-sm"
                >
                  <ArrowPathIcon className={clsx(
                    "w-4 h-4",
                    atualizarDadosMutation.isPending && "animate-spin"
                  )} />
                  {atualizarDadosMutation.isPending ? 'Iniciando...' : 'Atualizar Dados'}
                </button>
              )}
              <div className={clsx(
                'status-indicator',
                statusDados?.disponivel ? 'text-green-600' : 'text-yellow-600'
              )}>
                <span className={clsx(
                  'status-dot',
                  statusDados?.disponivel ? 'status-dot-success' : 'status-dot-warning'
                )} />
                <span className="text-sm font-medium">
                  {statusDados?.disponivel ? 'Disponível' : 'Indisponível'}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="card-body">
          {/* Barra de Progresso - mostrar quando downloading */}
          {isAdmin && progressoDownload?.status === 'downloading' && (
            <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <ArrowPathIcon className="w-5 h-5 text-blue-600 animate-spin" />
                  <span className="font-semibold text-blue-800">Download em Andamento</span>
                </div>
                <span className="text-sm font-bold text-blue-600">{progressoDownload.percent}%</span>
              </div>
              
              {/* Barra de progresso */}
              <div className="w-full bg-blue-200 rounded-full h-3 mb-2">
                <div 
                  className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${progressoDownload.percent}%` }}
                />
              </div>
              
              <div className="flex justify-between text-sm text-blue-700">
                <span>{progressoDownload.message}</span>
                <span>
                  {progressoDownload.current.toLocaleString('pt-BR')} / {progressoDownload.total.toLocaleString('pt-BR')}
                </span>
              </div>
            </div>
          )}

          {statusDados?.disponivel ? (
            <div className="flex items-start gap-4">
              <div className="stat-icon bg-gradient-to-br from-green-100 to-green-50 dark:from-green-900/50 dark:to-green-800/30">
                <CheckCircleIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <div className="flex-1">
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  Dados Disponíveis
                </p>
                <p className="text-gray-600 dark:text-gray-400 mt-1">
                  {statusDados.total_registros?.toLocaleString('pt-BR')} registros disponíveis
                  {statusDados.ultima_atualizacao && (
                    <> • Última atualização: {new Date(statusDados.ultima_atualizacao).toLocaleString('pt-BR')}</>
                  )}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-4">
              <div className="stat-icon bg-gradient-to-br from-yellow-100 to-yellow-50 dark:from-yellow-900/50 dark:to-yellow-800/30">
                <ExclamationTriangleIcon className="w-6 h-6 text-yellow-600 dark:text-yellow-400" />
              </div>
              <div className="flex-1">
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  Dados Não Disponíveis
                </p>
                <p className="text-gray-600 dark:text-gray-400 mt-1">
                  {isAdmin ? 'Clique em "Atualizar Dados" para baixar os dados mais recentes' : 'Aguarde o administrador atualizar os dados'}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="animate-slide-up">
        <h2 className="text-2xl font-display font-bold text-gray-900 dark:text-white mb-4">
          Acesso Rápido
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link to="/consulta" className="card-hover group">
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="stat-icon bg-gradient-to-br from-primary-100 to-primary-50 dark:from-primary-900/50 dark:to-primary-800/30 group-hover:scale-110 transition-transform">
                  <BoltIcon className="w-6 h-6 text-primary-700 dark:text-primary-400" />
                </div>
              </div>
              <h3 className="font-display font-bold text-gray-900 dark:text-white mb-1">
                Consulta BDGD
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Pesquisar dados de clientes cativos e livres
              </p>
              <div className="mt-4 text-primary-600 dark:text-primary-400 text-sm font-semibold group-hover:translate-x-1 transition-transform">
                Acessar →
              </div>
            </div>
          </Link>
          
          <Link to="/tarifas" className="card-hover group">
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="stat-icon bg-gradient-to-br from-green-100 to-green-50 dark:from-green-900/50 dark:to-green-800/30 group-hover:scale-110 transition-transform">
                  <SunIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
              </div>
              <h3 className="font-display font-bold text-gray-900 dark:text-white mb-1">
                Tarifas
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Consultar tarifas de energia por distribuidora
              </p>
              <div className="mt-4 text-primary-600 dark:text-primary-400 text-sm font-semibold group-hover:translate-x-1 transition-transform">
                Acessar →
              </div>
            </div>
          </Link>
          
          <Link to="/mapa" className="card-hover group">
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="stat-icon bg-gradient-to-br from-purple-100 to-purple-50 dark:from-purple-900/50 dark:to-purple-800/30 group-hover:scale-110 transition-transform">
                  <MapPinIcon className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
              </div>
              <h3 className="font-display font-bold text-gray-900 dark:text-white mb-1">
                Mapa
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Visualizar localização com Street View
              </p>
              <div className="mt-4 text-primary-600 dark:text-primary-400 text-sm font-semibold group-hover:translate-x-1 transition-transform">
                Acessar →
              </div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  )
}

// Helper function
function clsx(...classes: any[]) {
  return classes.filter(Boolean).join(' ')
}
