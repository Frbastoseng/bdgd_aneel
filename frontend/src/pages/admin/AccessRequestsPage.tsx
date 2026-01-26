import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/services/api'
import type { AccessRequest } from '@/types'
import toast from 'react-hot-toast'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import {
  CheckIcon,
  XMarkIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'

export default function AccessRequestsPage() {
  const queryClient = useQueryClient()
  const [reviewingId, setReviewingId] = useState<number | null>(null)
  const [response, setResponse] = useState('')
  
  const { data, isLoading } = useQuery({
    queryKey: ['access-requests'],
    queryFn: () => adminApi.accessRequests(),
  })
  
  const reviewMutation = useMutation({
    mutationFn: ({ requestId, status, adminResponse }: { 
      requestId: number
      status: string
      adminResponse?: string 
    }) => adminApi.reviewRequest(requestId, status, adminResponse),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['access-requests'] })
      queryClient.invalidateQueries({ queryKey: ['admin-stats'] })
      toast.success('Solicitação processada com sucesso')
      setReviewingId(null)
      setResponse('')
    },
    onError: () => {
      toast.error('Erro ao processar solicitação')
    },
  })
  
  const handleApprove = (requestId: number) => {
    reviewMutation.mutate({
      requestId,
      status: 'approved',
      adminResponse: response || 'Acesso aprovado',
    })
  }
  
  const handleReject = (requestId: number) => {
    if (!response) {
      toast.error('Por favor, forneça um motivo para a rejeição')
      return
    }
    reviewMutation.mutate({
      requestId,
      status: 'rejected',
      adminResponse: response,
    })
  }
  
  const requests: AccessRequest[] = data?.requests || []
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="spinner w-8 h-8 text-primary-600" />
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Solicitações de Acesso</h1>
        <p className="text-gray-600">
          Revise e aprove ou rejeite solicitações de novos usuários
        </p>
      </div>
      
      {/* Lista de Solicitações */}
      {requests.length === 0 ? (
        <div className="card p-12 text-center">
          <ClockIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Nenhuma solicitação pendente
          </h3>
          <p className="text-gray-600">
            Todas as solicitações foram processadas
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {requests.map((request) => (
            <div key={request.id} className="card">
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      {request.user_name}
                    </h3>
                    <p className="text-sm text-gray-600">
                      {request.user_email}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Solicitado em{' '}
                      {format(new Date(request.created_at), "dd 'de' MMMM 'de' yyyy 'às' HH:mm", { locale: ptBR })}
                    </p>
                  </div>
                  
                  <span className="badge badge-warning">
                    Pendente
                  </span>
                </div>
                
                {request.message && (
                  <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                    <p className="text-sm text-gray-700">
                      <strong>Mensagem:</strong> {request.message}
                    </p>
                  </div>
                )}
                
                {/* Formulário de resposta */}
                {reviewingId === request.id ? (
                  <div className="mt-4 space-y-4">
                    <div>
                      <label className="label">Resposta para o usuário</label>
                      <textarea
                        className="input resize-none"
                        rows={3}
                        placeholder="Digite uma mensagem para o usuário..."
                        value={response}
                        onChange={(e) => setResponse(e.target.value)}
                      />
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => handleApprove(request.id)}
                        disabled={reviewMutation.isPending}
                        className="btn-success"
                      >
                        <CheckIcon className="w-5 h-5 mr-2" />
                        Aprovar
                      </button>
                      <button
                        onClick={() => handleReject(request.id)}
                        disabled={reviewMutation.isPending}
                        className="btn-danger"
                      >
                        <XMarkIcon className="w-5 h-5 mr-2" />
                        Rejeitar
                      </button>
                      <button
                        onClick={() => {
                          setReviewingId(null)
                          setResponse('')
                        }}
                        className="btn-secondary"
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-4 flex items-center gap-3">
                    <button
                      onClick={() => setReviewingId(request.id)}
                      className="btn-primary"
                    >
                      Revisar Solicitação
                    </button>
                    <button
                      onClick={() => {
                        reviewMutation.mutate({
                          requestId: request.id,
                          status: 'approved',
                          adminResponse: 'Acesso aprovado',
                        })
                      }}
                      disabled={reviewMutation.isPending}
                      className="btn-success"
                    >
                      <CheckIcon className="w-5 h-5 mr-2" />
                      Aprovar Rápido
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
