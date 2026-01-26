import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { aneelApi } from '@/services/api'
import type { FiltroTarifas, TarifasResponse, OpcoesFiltrosTarifas } from '@/types'
import toast from 'react-hot-toast'
import { MagnifyingGlassIcon, ArrowPathIcon } from '@heroicons/react/24/outline'

export default function TarifasPage() {
  const [resultados, setResultados] = useState<TarifasResponse | null>(null)
  
  const { register, handleSubmit, reset } = useForm<FiltroTarifas>({
    defaultValues: {
      apenas_ultima_tarifa: false,
    },
  })
  
  const { data: opcoesFiltros } = useQuery<OpcoesFiltrosTarifas>({
    queryKey: ['opcoes-filtros-tarifas'],
    queryFn: aneelApi.opcoesFiltrosTarifas,
  })
  
  const consultaMutation = useMutation({
    mutationFn: (filtros: FiltroTarifas) => aneelApi.consultaTarifas(filtros),
    onSuccess: (data) => {
      setResultados(data)
      toast.success(`${data.total} tarifas encontradas`)
    },
    onError: () => {
      toast.error('Erro ao consultar tarifas')
    },
  })
  
  const atualizarMutation = useMutation({
    mutationFn: aneelApi.atualizarTarifas,
    onSuccess: () => {
      toast.success('Atualização de tarifas iniciada')
    },
    onError: () => {
      toast.error('Erro ao atualizar tarifas')
    },
  })
  
  const onSubmit = (data: FiltroTarifas) => {
    consultaMutation.mutate(data)
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Consulta de Tarifas</h1>
          <p className="text-gray-600">
            Pesquise tarifas de energia das distribuidoras
          </p>
        </div>
        <button
          onClick={() => atualizarMutation.mutate()}
          disabled={atualizarMutation.isPending}
          className="btn-outline"
        >
          <ArrowPathIcon className="w-5 h-5 mr-2" />
          Atualizar Dados
        </button>
      </div>
      
      {/* Filtros */}
      <form onSubmit={handleSubmit(onSubmit)} className="card p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Distribuidora */}
          <div>
            <label className="label">Distribuidora</label>
            <select className="input" {...register('distribuidora')}>
              <option value="">Todas</option>
              {opcoesFiltros?.distribuidoras?.map((dist) => (
                <option key={dist} value={dist}>{dist}</option>
              ))}
            </select>
          </div>
          
          {/* Subgrupo */}
          <div>
            <label className="label">Subgrupo</label>
            <select className="input" {...register('subgrupo')}>
              <option value="">Todos</option>
              {opcoesFiltros?.subgrupos?.map((sub) => (
                <option key={sub} value={sub}>{sub}</option>
              ))}
            </select>
          </div>
          
          {/* Modalidade */}
          <div>
            <label className="label">Modalidade</label>
            <select className="input" {...register('modalidade')}>
              <option value="">Todas</option>
              {opcoesFiltros?.modalidades?.map((mod) => (
                <option key={mod} value={mod}>{mod}</option>
              ))}
            </select>
          </div>
          
          {/* Detalhe */}
          <div>
            <label className="label">Detalhe</label>
            <select className="input" {...register('detalhe')}>
              <option value="">Todos</option>
              {opcoesFiltros?.detalhes?.map((det) => (
                <option key={det} value={det}>{det}</option>
              ))}
            </select>
          </div>
        </div>
        
        {/* Última tarifa */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="apenas_ultima_tarifa"
            className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            {...register('apenas_ultima_tarifa')}
          />
          <label htmlFor="apenas_ultima_tarifa" className="text-sm text-gray-700">
            Mostrar apenas a última tarifa por distribuidora
          </label>
        </div>
        
        {/* Botões */}
        <div className="flex items-center gap-3 pt-4 border-t">
          <button
            type="submit"
            disabled={consultaMutation.isPending}
            className="btn-primary"
          >
            {consultaMutation.isPending ? (
              <span className="spinner" />
            ) : (
              <MagnifyingGlassIcon className="w-5 h-5" />
            )}
            <span className="ml-2">Buscar Tarifas</span>
          </button>
          
          <button
            type="button"
            onClick={() => reset()}
            className="btn-secondary"
          >
            Limpar Filtros
          </button>
        </div>
      </form>
      
      {/* Resultados */}
      {resultados && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-gray-900">
              Resultados
            </h2>
            <p className="text-sm text-gray-600">
              {resultados.total.toLocaleString('pt-BR')} tarifas encontradas
            </p>
          </div>
          
          {/* Tabela */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-y border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Distribuidora
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    REH
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Posto Tarifário
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Unidade
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    TUSD (R$)
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    TE (R$)
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Vigência
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {resultados.tarifas.map((tarifa, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {tarifa.sig_agente}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {tarifa.dsc_reh}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {tarifa.nom_posto_tarifario}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {tarifa.dsc_unidade_terciaria}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 text-right font-mono">
                      {tarifa.vlr_tusd?.toLocaleString('pt-BR', { 
                        minimumFractionDigits: 6,
                        maximumFractionDigits: 6 
                      })}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 text-right font-mono">
                      {tarifa.vlr_te?.toLocaleString('pt-BR', { 
                        minimumFractionDigits: 6,
                        maximumFractionDigits: 6 
                      })}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 text-center">
                      {tarifa.dat_fim_vigencia && 
                        new Date(tarifa.dat_fim_vigencia).toLocaleDateString('pt-BR')
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
