import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/services/api'
import type { User, UserStatus } from '@/types'
import toast from 'react-hot-toast'
import { format } from 'date-fns'
import clsx from 'clsx'
import {
  MagnifyingGlassIcon,
  UserIcon,
  NoSymbolIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline'

export default function UsersPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<UserStatus | ''>('')
  const [search, setSearch] = useState('')
  
  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page, statusFilter],
    queryFn: () => adminApi.users(page, 20, statusFilter || undefined),
  })
  
  const suspendMutation = useMutation({
    mutationFn: (userId: number) => adminApi.suspendUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success('Usuário suspenso')
    },
    onError: () => {
      toast.error('Erro ao suspender usuário')
    },
  })
  
  const activateMutation = useMutation({
    mutationFn: (userId: number) => adminApi.activateUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success('Usuário ativado')
    },
    onError: () => {
      toast.error('Erro ao ativar usuário')
    },
  })
  
  const users: User[] = data?.users || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / 20)
  
  const filteredUsers = users.filter((user) =>
    !search ||
    user.full_name.toLowerCase().includes(search.toLowerCase()) ||
    user.email.toLowerCase().includes(search.toLowerCase())
  )
  
  const getStatusBadge = (status: UserStatus) => {
    switch (status) {
      case 'approved':
        return <span className="badge badge-success">Aprovado</span>
      case 'pending':
        return <span className="badge badge-warning">Pendente</span>
      case 'rejected':
        return <span className="badge badge-danger">Rejeitado</span>
      case 'suspended':
        return <span className="badge badge-gray">Suspenso</span>
      default:
        return <span className="badge badge-gray">{status}</span>
    }
  }
  
  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'admin':
        return <span className="badge badge-info">Admin</span>
      case 'user':
        return <span className="badge badge-gray">Usuário</span>
      default:
        return <span className="badge badge-gray">{role}</span>
    }
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Gerenciar Usuários</h1>
          <p className="text-gray-600">
            {total} usuários cadastrados
          </p>
        </div>
      </div>
      
      {/* Filtros */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Buscar por nome ou email..."
                className="input pl-10"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          
          <div className="w-48">
            <select
              className="input"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as UserStatus | '')
                setPage(1)
              }}
            >
              <option value="">Todos os status</option>
              <option value="approved">Aprovados</option>
              <option value="pending">Pendentes</option>
              <option value="rejected">Rejeitados</option>
              <option value="suspended">Suspensos</option>
            </select>
          </div>
        </div>
      </div>
      
      {/* Tabela */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center p-12">
            <span className="spinner w-8 h-8 text-primary-600" />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Usuário
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Empresa
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Função
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Cadastro
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Ações
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {filteredUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className={clsx(
                            'w-10 h-10 rounded-full flex items-center justify-center',
                            user.is_active ? 'bg-primary-100' : 'bg-gray-100'
                          )}>
                            <UserIcon className={clsx(
                              'w-5 h-5',
                              user.is_active ? 'text-primary-600' : 'text-gray-400'
                            )} />
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">
                              {user.full_name}
                            </p>
                            <p className="text-sm text-gray-500">
                              {user.email}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {user.company || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getRoleBadge(user.role)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(user.status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {format(new Date(user.created_at), 'dd/MM/yyyy')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        {user.status === 'approved' && user.role !== 'admin' && (
                          <button
                            onClick={() => suspendMutation.mutate(user.id)}
                            disabled={suspendMutation.isPending}
                            className="btn-outline text-red-600 border-red-300 hover:bg-red-50 text-sm"
                          >
                            <NoSymbolIcon className="w-4 h-4 mr-1" />
                            Suspender
                          </button>
                        )}
                        {user.status === 'suspended' && (
                          <button
                            onClick={() => activateMutation.mutate(user.id)}
                            disabled={activateMutation.isPending}
                            className="btn-outline text-green-600 border-green-300 hover:bg-green-50 text-sm"
                          >
                            <CheckCircleIcon className="w-4 h-4 mr-1" />
                            Ativar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Paginação */}
            {totalPages > 1 && (
              <div className="px-6 py-4 border-t flex items-center justify-between">
                <p className="text-sm text-gray-600">
                  Página {page} de {totalPages}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="btn-outline text-sm"
                  >
                    Anterior
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="btn-outline text-sm"
                  >
                    Próxima
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
