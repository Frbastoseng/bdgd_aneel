import { useState, useEffect, useCallback, Fragment } from 'react'
import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { matchingApi } from '@/services/api'
import type { BdgdClienteComMatch, MatchItem, MatchingStats, MatchingPaginated } from '@/types'
import {
  MagnifyingGlassIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  LinkIcon,
  PhoneIcon,
  EnvelopeIcon,
  MapPinIcon,
  BuildingOffice2Icon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
} from '@heroicons/react/24/solid'

function formatCnpj(cnpj: string): string {
  if (!cnpj || cnpj.length !== 14) return cnpj || ''
  return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8, 12)}-${cnpj.slice(12)}`
}

function formatPhone(phone: string | null | undefined): string {
  if (!phone) return ''
  const digits = phone.replace(/\D/g, '')
  if (digits.length === 11) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
  }
  if (digits.length === 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`
  }
  return phone
}

function ScoreBadge({ score }: { score: number }) {
  if (score >= 75) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 dark:bg-green-900/30 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:text-green-300">
        <CheckCircleIcon className="h-3.5 w-3.5" />
        Alta ({score.toFixed(0)})
      </span>
    )
  }
  if (score >= 50) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 dark:bg-yellow-900/30 px-2.5 py-0.5 text-xs font-medium text-yellow-800 dark:text-yellow-300">
        <ExclamationTriangleIcon className="h-3.5 w-3.5" />
        Media ({score.toFixed(0)})
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 dark:bg-red-900/30 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:text-red-300">
      <XCircleIcon className="h-3.5 w-3.5" />
      Baixa ({score.toFixed(0)})
    </span>
  )
}

function ScoreBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = max > 0 ? (score / max) * 100 : 0
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 dark:text-gray-400 text-right">{label}</span>
      <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-gray-600 dark:text-gray-300 text-right font-mono">{score.toFixed(0)}/{max}</span>
    </div>
  )
}

function MatchDetail({ match }: { match: MatchItem }) {
  return (
    <div className="border dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-800">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-mono text-blue-600 dark:text-blue-400">{formatCnpj(match.cnpj)}</span>
            <span className="text-xs bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-gray-500 dark:text-gray-400">
              #{match.rank}
            </span>
          </div>
          <p className="text-sm font-semibold text-gray-900 dark:text-white mt-1">
            {match.razao_social}
          </p>
          {match.nome_fantasia && (
            <p className="text-xs text-gray-500 dark:text-gray-400">{match.nome_fantasia}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {match.address_source === 'geocoded' && (
            <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 dark:bg-purple-900/30 px-2 py-0.5 text-xs font-medium text-purple-800 dark:text-purple-300">
              <MapPinIcon className="h-3 w-3" />
              Via Geocode
            </span>
          )}
          <ScoreBadge score={match.score_total} />
        </div>
      </div>

      {/* Score breakdown */}
      <div className="space-y-1 mb-3">
        <ScoreBar label="CEP" score={match.score_cep} max={40} />
        <ScoreBar label="CNAE" score={match.score_cnae} max={25} />
        <ScoreBar label="Endereco" score={match.score_endereco} max={20} />
        <ScoreBar label="Numero" score={match.score_numero} max={10} />
        <ScoreBar label="Bairro" score={match.score_bairro} max={5} />
      </div>

      {/* Match details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-300">
        <div className="flex items-center gap-1">
          <MapPinIcon className="h-3.5 w-3.5 text-gray-400" />
          <span>
            {match.cnpj_logradouro}
            {match.cnpj_numero ? `, ${match.cnpj_numero}` : ''}
            {match.cnpj_bairro ? ` - ${match.cnpj_bairro}` : ''}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <BuildingOffice2Icon className="h-3.5 w-3.5 text-gray-400" />
          <span>
            {match.cnpj_municipio}/{match.cnpj_uf}
            {match.cnpj_cep ? ` - CEP ${match.cnpj_cep}` : ''}
          </span>
        </div>
        {match.cnpj_cnae_descricao && (
          <div className="flex items-center gap-1 md:col-span-2">
            <LinkIcon className="h-3.5 w-3.5 text-gray-400" />
            <span>CNAE: {match.cnpj_cnae} - {match.cnpj_cnae_descricao}</span>
          </div>
        )}
        {match.cnpj_telefone && (
          <div className="flex items-center gap-1">
            <PhoneIcon className="h-3.5 w-3.5 text-gray-400" />
            <a
              href={`https://wa.me/55${match.cnpj_telefone.replace(/\D/g, '')}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-green-600 dark:text-green-400 hover:underline"
            >
              {formatPhone(match.cnpj_telefone)}
            </a>
          </div>
        )}
        {match.cnpj_email && (
          <div className="flex items-center gap-1">
            <EnvelopeIcon className="h-3.5 w-3.5 text-gray-400" />
            <a
              href={`mailto:${match.cnpj_email}`}
              className="text-blue-600 dark:text-blue-400 hover:underline"
            >
              {match.cnpj_email}
            </a>
          </div>
        )}
      </div>
    </div>
  )
}

export default function MatchingPage() {
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [uf, setUf] = useState('')
  const [confianca, setConfianca] = useState('')
  const [page, setPage] = useState(1)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const perPage = 30
  const [refining, setRefining] = useState(false)
  const [refineResult, setRefineResult] = useState<{ refined: number; geocoded: number; improved: number } | null>(null)
  const queryClient = useQueryClient()

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 500)
    return () => clearTimeout(timer)
  }, [search])

  // Reset page on filter change
  useEffect(() => {
    setPage(1)
  }, [uf, confianca])

  const { data: stats, isLoading: statsLoading } = useQuery<MatchingStats>({
    queryKey: ['matching-stats'],
    queryFn: matchingApi.getStats,
    staleTime: 60000,
  })

  const { data: results, isLoading: resultsLoading, isFetching } = useQuery<MatchingPaginated>({
    queryKey: ['matching-results', debouncedSearch, uf, confianca, page],
    queryFn: () =>
      matchingApi.getResults({
        search: debouncedSearch || undefined,
        uf: uf || undefined,
        confianca: confianca || undefined,
        page,
        per_page: perPage,
      }),
    placeholderData: keepPreviousData,
    staleTime: 30000,
  })

  const totalPages = results ? Math.ceil(results.total / perPage) : 0

  const toggleExpand = useCallback((codId: string) => {
    setExpandedRow((prev) => (prev === codId ? null : codId))
  }, [])

  const handleRefine = useCallback(async () => {
    if (!results?.data?.length || refining) return
    const codIds = results.data.map((c: BdgdClienteComMatch) => c.cod_id)
    setRefining(true)
    setRefineResult(null)
    try {
      const result = await matchingApi.refineMatches(codIds)
      setRefineResult(result)
      // Recarregar dados após refinamento
      queryClient.invalidateQueries({ queryKey: ['matching-results'] })
      queryClient.invalidateQueries({ queryKey: ['matching-stats'] })
    } catch {
      setRefineResult({ refined: 0, geocoded: 0, improved: -1 })
    } finally {
      setRefining(false)
    }
  }, [results, refining, queryClient])

  const UFS = [
    'AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT',
    'PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO',
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Matching BDGD - CNPJ
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Descoberta automatica de CNPJs para clientes BDGD por CEP, CNAE, endereco, bairro e coordenadas geocodificadas
        </p>
      </div>

      {/* Stats Cards */}
      {!statsLoading && stats && (
        <div className={`grid grid-cols-2 md:grid-cols-4 ${stats.via_geocode ? 'lg:grid-cols-8' : 'lg:grid-cols-7'} gap-3`}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Total Clientes</p>
            <p className="text-lg font-bold text-gray-900 dark:text-white">
              {stats.total_clientes.toLocaleString('pt-BR')}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Com Match</p>
            <p className="text-lg font-bold text-green-600 dark:text-green-400">
              {stats.clientes_com_match.toLocaleString('pt-BR')}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Sem Match</p>
            <p className="text-lg font-bold text-red-600 dark:text-red-400">
              {stats.clientes_sem_match.toLocaleString('pt-BR')}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">Score Medio</p>
            <p className="text-lg font-bold text-blue-600 dark:text-blue-400">
              {stats.avg_score_top1?.toFixed(1) ?? '-'}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
            <p className="text-xs text-green-600 dark:text-green-400">Alta Confianca</p>
            <p className="text-lg font-bold text-green-600 dark:text-green-400">
              {stats.alta_confianca.toLocaleString('pt-BR')}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
            <p className="text-xs text-yellow-600 dark:text-yellow-400">Media Confianca</p>
            <p className="text-lg font-bold text-yellow-600 dark:text-yellow-400">
              {stats.media_confianca.toLocaleString('pt-BR')}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
            <p className="text-xs text-red-600 dark:text-red-400">Baixa Confianca</p>
            <p className="text-lg font-bold text-red-600 dark:text-red-400">
              {stats.baixa_confianca.toLocaleString('pt-BR')}
            </p>
          </div>
          {(stats.via_geocode ?? 0) > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
              <p className="text-xs text-purple-600 dark:text-purple-400">Via Geocode</p>
              <p className="text-lg font-bold text-purple-600 dark:text-purple-400">
                {stats.via_geocode?.toLocaleString('pt-BR')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar por empresa, CNPJ, endereco, municipio..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <select
          value={uf}
          onChange={(e) => setUf(e.target.value)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="">Todas UFs</option>
          {UFS.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <select
          value={confianca}
          onChange={(e) => setConfianca(e.target.value)}
          className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
        >
          <option value="">Todas confiancias</option>
          <option value="alta">Alta (75+)</option>
          <option value="media">Media (50-74)</option>
          <option value="baixa">Baixa (15-49)</option>
        </select>
      </div>

      {/* Results count + Afinar Busca */}
      {results && (
        <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
          <div className="flex items-center gap-3">
            <span>
              {results.total.toLocaleString('pt-BR')} clientes encontrados
              {isFetching && ' (atualizando...)'}
            </span>
            {results.data?.length > 0 && (
              <button
                onClick={handleRefine}
                disabled={refining}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="Geocodifica coordenadas e re-faz matching para melhorar os scores desta pagina"
              >
                <ArrowPathIcon className={`h-3.5 w-3.5 ${refining ? 'animate-spin' : ''}`} />
                {refining ? 'Afinando...' : 'Afinar Busca'}
              </button>
            )}
          </div>
          <span>
            Pagina {page} de {totalPages}
          </span>
        </div>
      )}

      {/* Refine result feedback */}
      {refineResult && (
        <div className={`rounded-lg p-3 text-sm ${
          refineResult.improved === -1
            ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
            : 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300'
        }`}>
          {refineResult.improved === -1 ? (
            <span>Erro ao refinar busca. Tente novamente.</span>
          ) : (
            <span>
              Refinamento concluido: <strong>{refineResult.refined}</strong> clientes processados,{' '}
              <strong>{refineResult.geocoded}</strong> novos enderecos geocodificados,{' '}
              <strong>{refineResult.improved}</strong> scores melhorados.
            </span>
          )}
          <button
            onClick={() => setRefineResult(null)}
            className="ml-2 text-xs underline hover:no-underline"
          >
            fechar
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
        {resultsLoading ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            Carregando resultados...
          </div>
        ) : results?.data?.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            Nenhum resultado encontrado. Execute o matching primeiro.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-8"></th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Cliente BDGD</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Endereco BDGD</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">CEP</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">CNAE</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Melhor Match</th>
                  <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {results?.data?.map((cliente: BdgdClienteComMatch) => {
                  const isExpanded = expandedRow === cliente.cod_id
                  const bestMatch = cliente.matches?.[0]
                  return (
                    <Fragment key={cliente.cod_id}>
                      <tr
                        className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
                        onClick={() => toggleExpand(cliente.cod_id)}
                      >
                        <td className="px-3 py-3">
                          {isExpanded ? (
                            <ChevronUpIcon className="h-4 w-4 text-gray-400" />
                          ) : (
                            <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <div className="text-xs font-mono text-gray-500 dark:text-gray-400">
                            {cliente.cod_id.slice(0, 15)}...
                          </div>
                          <div className="text-xs text-gray-600 dark:text-gray-300">
                            {cliente.municipio_nome}/{cliente.uf}
                          </div>
                          <div className="text-xs text-gray-400">
                            {cliente.clas_sub} | {cliente.gru_tar}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-xs text-gray-600 dark:text-gray-300 max-w-[200px] truncate">
                          {cliente.lgrd_original}
                          {cliente.brr_original ? ` - ${cliente.brr_original}` : ''}
                        </td>
                        <td className="px-3 py-3 text-xs font-mono text-gray-600 dark:text-gray-300">
                          {cliente.cep_original}
                        </td>
                        <td className="px-3 py-3 text-xs font-mono text-gray-600 dark:text-gray-300">
                          {cliente.cnae_original}
                        </td>
                        <td className="px-3 py-3">
                          {bestMatch ? (
                            <div>
                              <p className="text-xs font-medium text-gray-900 dark:text-white truncate max-w-[200px]">
                                {bestMatch.razao_social}
                              </p>
                              <p className="text-xs font-mono text-blue-600 dark:text-blue-400">
                                {formatCnpj(bestMatch.cnpj)}
                              </p>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-400">-</span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-center">
                          {cliente.best_score != null && (
                            <ScoreBadge score={cliente.best_score} />
                          )}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr>
                          <td colSpan={7} className="px-6 py-4 bg-gray-50 dark:bg-gray-900/50">
                            {/* BDGD Client Info */}
                            <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                              <h4 className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">
                                Dados BDGD do Cliente
                              </h4>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                <div>
                                  <span className="text-gray-500 dark:text-gray-400">Endereco:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{cliente.lgrd_original}</span>
                                </div>
                                <div>
                                  <span className="text-gray-500 dark:text-gray-400">Bairro:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{cliente.brr_original}</span>
                                </div>
                                <div>
                                  <span className="text-gray-500 dark:text-gray-400">CEP:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{cliente.cep_original}</span>
                                </div>
                                <div>
                                  <span className="text-gray-500 dark:text-gray-400">CNAE:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{cliente.cnae_original}</span>
                                </div>
                                <div>
                                  <span className="text-gray-500 dark:text-gray-400">Classe:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{cliente.clas_sub}</span>
                                </div>
                                <div>
                                  <span className="text-gray-500 dark:text-gray-400">Grupo:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{cliente.gru_tar}</span>
                                </div>
                                <div>
                                  <span className="text-gray-500 dark:text-gray-400">Demanda:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">{cliente.dem_cont?.toFixed(1)} kW</span>
                                </div>
                                <div>
                                  <span className="text-gray-500 dark:text-gray-400">Tipo:</span>{' '}
                                  <span className="text-gray-900 dark:text-white">
                                    {cliente.liv === 1 ? 'Livre' : 'Cativo'}
                                    {cliente.possui_solar ? ' | Solar' : ''}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* Endereço Geocodificado */}
                            {cliente.geo_cep && (
                              <div className="mb-4 p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                                <h4 className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2 flex items-center gap-1">
                                  <MapPinIcon className="h-4 w-4" />
                                  Endereco Geocodificado (via coordenadas)
                                </h4>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                  {cliente.geo_logradouro && (
                                    <div>
                                      <span className="text-gray-500 dark:text-gray-400">Logradouro:</span>{' '}
                                      <span className="text-gray-900 dark:text-white">{cliente.geo_logradouro}</span>
                                    </div>
                                  )}
                                  {cliente.geo_bairro && (
                                    <div>
                                      <span className="text-gray-500 dark:text-gray-400">Bairro:</span>{' '}
                                      <span className="text-gray-900 dark:text-white">{cliente.geo_bairro}</span>
                                    </div>
                                  )}
                                  <div>
                                    <span className="text-gray-500 dark:text-gray-400">CEP:</span>{' '}
                                    <span className={`font-mono ${
                                      cliente.cep_original && cliente.geo_cep !== cliente.cep_original?.replace(/\D/g, '')
                                        ? 'text-orange-600 dark:text-orange-400 font-semibold'
                                        : 'text-gray-900 dark:text-white'
                                    }`}>
                                      {cliente.geo_cep}
                                      {cliente.cep_original && cliente.geo_cep !== cliente.cep_original?.replace(/\D/g, '') && (
                                        <span className="ml-1 text-orange-500" title="CEP diferente do BDGD">*</span>
                                      )}
                                    </span>
                                  </div>
                                  {cliente.geo_municipio && (
                                    <div>
                                      <span className="text-gray-500 dark:text-gray-400">Municipio:</span>{' '}
                                      <span className="text-gray-900 dark:text-white">{cliente.geo_municipio}/{cliente.geo_uf}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Matches */}
                            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                              CNPJs Candidatos ({cliente.matches?.length || 0})
                            </h4>
                            <div className="space-y-3">
                              {cliente.matches?.map((match) => (
                                <MatchDetail key={`${match.cnpj}-${match.rank}`} match={match} />
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(1)}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
          >
            Primeira
          </button>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
          >
            <ChevronLeftIcon className="h-4 w-4" />
          </button>
          <span className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
          >
            <ChevronRightIcon className="h-4 w-4" />
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-50 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
          >
            Ultima
          </button>
        </div>
      )}
    </div>
  )
}
