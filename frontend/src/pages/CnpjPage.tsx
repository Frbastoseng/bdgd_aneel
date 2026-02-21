import { useState, useEffect, useCallback } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  BuildingOffice2Icon,
  MapPinIcon,
  PhoneIcon,
  EnvelopeIcon,
  UserGroupIcon,
  BriefcaseIcon,
  CheckCircleIcon,
  XCircleIcon,
  BuildingLibraryIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { cnpjApi } from '@/services/api'
import type {
  CnpjCacheItem,
  CnpjCacheDetail,
  CnpjCachePaginated,
  CnpjCacheStats,
} from '@/types'

const PER_PAGE = 50

const UF_LIST = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS',
  'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC',
  'SE', 'SP', 'TO',
]

// ── Utility functions ─────────────────────────────────────────────────

function fmtNum(n: number | null | undefined): string {
  if (n == null) return '0'
  return n.toLocaleString('pt-BR')
}

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

function formatCnpj(cnpj: string): string {
  if (cnpj.length !== 14) return cnpj
  return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8, 12)}-${cnpj.slice(12)}`
}

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '-'
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatCep(cep: string | null | undefined): string {
  if (!cep) return '-'
  const digits = cep.replace(/\D/g, '')
  if (digits.length !== 8) return cep
  return `${digits.slice(0, 5)}-${digits.slice(5)}`
}

function formatDate(date: string | null | undefined): string {
  if (!date) return '-'
  if (date.length === 10 && date.includes('-')) {
    const [y, m, d] = date.split('-')
    return `${d}/${m}/${y}`
  }
  return date
}

function toWhatsAppUrl(phone: string): string {
  const digits = phone.replace(/\D/g, '')
  const number = digits.startsWith('55') ? digits : `55${digits}`
  return `https://wa.me/${number}`
}

// ── Small components ──────────────────────────────────────────────────

function SituacaoBadge({ situacao }: { situacao: string | null | undefined }) {
  if (!situacao) return <span className="text-sm text-gray-400">-</span>
  const lower = situacao.toLowerCase()
  const isAtiva = lower.includes('ativa')
  const isBaixa = lower.includes('baixa')

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
        isAtiva && 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
        isBaixa && 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
        !isAtiva && !isBaixa && 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
      )}
    >
      {isAtiva ? <CheckCircleIcon className="h-3.5 w-3.5" /> : <XCircleIcon className="h-3.5 w-3.5" />}
      {situacao}
    </span>
  )
}

function SectionHeader({ icon: Icon, label }: { icon: React.ElementType; label: string }) {
  return (
    <div className="flex items-center gap-1.5 border-b border-gray-200 dark:border-gray-700 pb-1.5 mb-2">
      <Icon className="h-4 w-4 text-gray-400" />
      <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
        {label}
      </p>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === '' || value === '-') return null
  return (
    <div className="flex gap-2 py-0.5 text-sm">
      <span className="shrink-0 text-gray-500 dark:text-gray-400">{label}:</span>
      <span className="font-medium text-gray-900 dark:text-white">{value}</span>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className={clsx(
      'rounded-xl border px-5 py-4',
      color === 'blue' && 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20',
      color === 'green' && 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20',
    )}>
      <p className="text-sm text-gray-600 dark:text-gray-400">{label}</p>
      <p className={clsx(
        'text-2xl font-bold mt-1',
        color === 'blue' && 'text-blue-700 dark:text-blue-400',
        color === 'green' && 'text-green-700 dark:text-green-400',
      )}>{value}</p>
    </div>
  )
}

// ── Expanded row detail ───────────────────────────────────────────────

function ExpandedRow({ cnpj }: { cnpj: string }) {
  const { data: detail, isLoading } = useQuery<CnpjCacheDetail>({
    queryKey: ['cnpj-detail', cnpj],
    queryFn: () => cnpjApi.getCnpjCacheDetail(cnpj),
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading) {
    return (
      <tr>
        <td colSpan={9} className="px-6 py-8">
          <div className="flex items-center justify-center gap-2 text-gray-500">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600" />
            Carregando detalhes...
          </div>
        </td>
      </tr>
    )
  }

  if (!detail) return null

  const address = [
    detail.descricao_tipo_logradouro,
    detail.logradouro,
    detail.numero ? `n. ${detail.numero}` : null,
    detail.complemento,
  ].filter(Boolean).join(', ')

  return (
    <tr>
      <td colSpan={9} className="px-4 py-0">
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-5 my-2 space-y-5 animate-fade-in">
          {/* Row 1: Dados Cadastrais + Situacao + Contato */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Dados Cadastrais */}
            <div>
              <SectionHeader icon={BuildingOffice2Icon} label="Dados Cadastrais" />
              <InfoRow label="CNPJ" value={formatCnpj(detail.cnpj)} />
              <InfoRow label="Razao Social" value={detail.razao_social} />
              <InfoRow label="Nome Fantasia" value={detail.nome_fantasia} />
              <InfoRow label="Tipo" value={detail.identificador_matriz_filial} />
              <InfoRow label="Abertura" value={formatDate(detail.data_inicio_atividade)} />
              <InfoRow label="Natureza Juridica" value={detail.natureza_juridica} />
              <InfoRow label="Porte" value={detail.porte} />
              <InfoRow label="Capital Social" value={formatCurrency(detail.capital_social)} />
            </div>

            {/* Situacao Cadastral */}
            <div>
              <SectionHeader icon={CheckCircleIcon} label="Situacao Cadastral" />
              <div className="py-1">
                <SituacaoBadge situacao={detail.situacao_cadastral} />
              </div>
              <InfoRow label="Data" value={formatDate(detail.data_situacao_cadastral)} />
              <InfoRow label="Motivo" value={detail.motivo_situacao_cadastral} />
              {detail.situacao_especial && (
                <InfoRow label="Situacao Especial" value={detail.situacao_especial} />
              )}

              <div className="mt-3">
                <SectionHeader icon={BuildingLibraryIcon} label="Regime Tributario" />
                <div className="flex flex-wrap gap-2 mt-1">
                  <span className={clsx(
                    'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                    detail.opcao_pelo_simples === 'S'
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
                  )}>
                    Simples: {detail.opcao_pelo_simples === 'S' ? 'Sim' : 'Nao'}
                  </span>
                  <span className={clsx(
                    'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                    detail.opcao_pelo_mei === 'S'
                      ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
                  )}>
                    MEI: {detail.opcao_pelo_mei === 'S' ? 'Sim' : 'Nao'}
                  </span>
                </div>
                {detail.regime_tributario && detail.regime_tributario.length > 0 && (
                  <div className="mt-2 text-xs text-gray-500 space-y-0.5">
                    {detail.regime_tributario.map((r, i) => (
                      <div key={i}>{r.ano}: {r.forma_de_tributacao}</div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Contato */}
            <div>
              <SectionHeader icon={PhoneIcon} label="Contato" />
              {detail.telefone_1 && (
                <div className="flex items-center gap-2 py-0.5 text-sm">
                  <PhoneIcon className="h-4 w-4 text-gray-400" />
                  <span className="font-medium text-gray-900 dark:text-white">{detail.telefone_1}</span>
                  <a
                    href={toWhatsAppUrl(detail.telefone_1)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-green-600 hover:text-green-700 text-xs font-medium"
                  >
                    WhatsApp
                  </a>
                </div>
              )}
              {detail.telefone_2 && (
                <div className="flex items-center gap-2 py-0.5 text-sm">
                  <PhoneIcon className="h-4 w-4 text-gray-400" />
                  <span className="font-medium text-gray-900 dark:text-white">{detail.telefone_2}</span>
                </div>
              )}
              {detail.email && (
                <div className="flex items-center gap-2 py-0.5 text-sm">
                  <EnvelopeIcon className="h-4 w-4 text-gray-400" />
                  <a
                    href={`mailto:${detail.email}`}
                    className="font-medium text-primary-600 hover:text-primary-700"
                  >
                    {detail.email}
                  </a>
                </div>
              )}

              <div className="mt-4">
                <SectionHeader icon={MapPinIcon} label="Endereco" />
                <InfoRow label="Logradouro" value={address || detail.logradouro} />
                <InfoRow label="Bairro" value={detail.bairro} />
                <InfoRow label="Cidade/UF" value={detail.municipio ? `${detail.municipio}/${detail.uf}` : null} />
                <InfoRow label="CEP" value={formatCep(detail.cep)} />
                {detail.nome_cidade_exterior && (
                  <InfoRow label="Exterior" value={`${detail.nome_cidade_exterior} - ${detail.pais}`} />
                )}
              </div>
            </div>
          </div>

          {/* Row 2: CNAE */}
          <div>
            <SectionHeader icon={BriefcaseIcon} label="Atividade Economica" />
            <InfoRow label="CNAE Principal" value={
              detail.cnae_fiscal
                ? `${detail.cnae_fiscal} - ${detail.cnae_fiscal_descricao}`
                : detail.cnae_fiscal_descricao
            } />
            {detail.cnaes_secundarios && detail.cnaes_secundarios.length > 0 && (
              <div className="mt-2">
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                  CNAEs Secundarios ({detail.cnaes_secundarios.length}):
                </p>
                <div className="max-h-32 overflow-y-auto space-y-0.5">
                  {detail.cnaes_secundarios.map((c, i) => (
                    <p key={i} className="text-xs text-gray-600 dark:text-gray-400">
                      {c.codigo} - {c.descricao}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Row 3: QSA */}
          {detail.socios_detalhados && detail.socios_detalhados.length > 0 && (
            <div>
              <SectionHeader icon={UserGroupIcon} label="Quadro Societario" />
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500 dark:text-gray-400 uppercase">
                      <th className="pb-2 pr-4 font-medium">Nome</th>
                      <th className="pb-2 pr-4 font-medium">Qualificacao</th>
                      <th className="pb-2 pr-4 font-medium">Entrada</th>
                      <th className="pb-2 pr-4 font-medium">Faixa Etaria</th>
                      <th className="pb-2 pr-4 font-medium">CPF/CNPJ</th>
                      <th className="pb-2 font-medium">Rep. Legal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {detail.socios_detalhados.map((s, i) => (
                      <tr key={i}>
                        <td className="py-1.5 pr-4 font-medium text-gray-900 dark:text-white">{s.nome}</td>
                        <td className="py-1.5 pr-4 text-gray-600 dark:text-gray-400">{s.qualificacao}</td>
                        <td className="py-1.5 pr-4 text-gray-600 dark:text-gray-400">{formatDate(s.data_entrada_sociedade)}</td>
                        <td className="py-1.5 pr-4 text-gray-600 dark:text-gray-400">{s.faixa_etaria || '-'}</td>
                        <td className="py-1.5 pr-4 text-gray-600 dark:text-gray-400">{s.cnpj_cpf || '-'}</td>
                        <td className="py-1.5 text-gray-600 dark:text-gray-400">{s.nome_representante_legal || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Socios simples como fallback */}
          {!detail.socios_detalhados && detail.socios && detail.socios.length > 0 && (
            <div>
              <SectionHeader icon={UserGroupIcon} label="Socios" />
              <div className="space-y-1">
                {detail.socios.map((s, i) => (
                  <p key={i} className="text-sm text-gray-700 dark:text-gray-300">
                    <span className="font-medium">{s.nome}</span> - {s.qualificacao}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Cache info */}
          {detail.data_consulta_formatada && (
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              <ClockIcon className="h-3.5 w-3.5" />
              Ultima consulta: {detail.data_consulta_formatada}
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}

// ── Main page ─────────────────────────────────────────────────────────

export default function CnpjPage() {
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 500)
  const [ufFilter, setUfFilter] = useState('')
  const [page, setPage] = useState(1)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  // Reset page on filter change
  useEffect(() => { setPage(1) }, [debouncedSearch, ufFilter])

  const toggleExpanded = useCallback((cnpj: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(cnpj)) next.delete(cnpj)
      else next.add(cnpj)
      return next
    })
  }, [])

  // Queries
  const { data: stats } = useQuery<CnpjCacheStats>({
    queryKey: ['cnpj-stats'],
    queryFn: cnpjApi.getCnpjCacheStats,
    staleTime: 2 * 60 * 1000,
  })

  const { data: cacheData, isLoading, isFetching } = useQuery<CnpjCachePaginated>({
    queryKey: ['cnpj-cache', debouncedSearch, ufFilter, page],
    queryFn: () => cnpjApi.getCnpjCache({
      search: debouncedSearch || undefined,
      uf: ufFilter || undefined,
      page,
      per_page: PER_PAGE,
    }),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  })

  const items = cacheData?.data ?? []
  const total = cacheData?.total ?? 0
  const totalPages = Math.ceil(total / PER_PAGE)
  const showing = items.length > 0
    ? `${(page - 1) * PER_PAGE + 1}-${(page - 1) * PER_PAGE + items.length} de ${total > 10000 ? '10.000+' : fmtNum(total)}`
    : '0'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-bold text-gray-900 dark:text-white">
          Cadastro CNPJ
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Base de dados de empresas da Receita Federal
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatCard label="Total de Empresas" value={fmtNum(stats.total)} color="blue" />
          <StatCard label="Empresas Ativas" value={fmtNum(stats.ativas)} color="green" />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por empresa, CNPJ, cidade, CNAE..."
            className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 pl-10 pr-10 py-2.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          )}
        </div>

        <select
          value={ufFilter}
          onChange={(e) => setUfFilter(e.target.value)}
          className="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2.5 text-sm text-gray-900 dark:text-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-colors"
        >
          <option value="">Todos os estados</option>
          {UF_LIST.map(uf => (
            <option key={uf} value={uf}>{uf}</option>
          ))}
        </select>
      </div>

      {/* Loading indicator */}
      {isFetching && !isLoading && (
        <div className="flex items-center gap-2 text-sm text-primary-600">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-200 border-t-primary-600" />
          Atualizando...
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        {isLoading ? (
          <div className="space-y-0">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 border-b border-gray-100 dark:border-gray-700 px-4 py-3.5 last:border-0">
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                <div className="h-4 w-44 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                <div className="h-4 w-28 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                <div className="h-5 w-24 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center">
            <BuildingOffice2Icon className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
            <p className="mt-3 text-gray-500 dark:text-gray-400">
              {debouncedSearch || ufFilter ? 'Nenhum resultado encontrado.' : 'Nenhum CNPJ cadastrado.'}
            </p>
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900/50">
              <tr>
                <th className="w-10 px-3 py-3" />
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">CNPJ</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Razao Social</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hidden lg:table-cell">Nome Fantasia</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hidden md:table-cell">Cidade/UF</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hidden xl:table-cell">CNAE</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hidden xl:table-cell">Porte</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Situacao</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
              {items.map((item) => {
                const isExpanded = expandedIds.has(item.cnpj)
                return (
                  <TableRowGroup key={item.cnpj} item={item} isExpanded={isExpanded} onToggle={toggleExpanded} />
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Mostrando {showing}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(1)}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Primeira
            </button>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Anterior
            </button>
            <span className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 tabular-nums">
              {page} / {totalPages > 200 ? '200+' : totalPages}
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page >= totalPages}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Proxima
            </button>
            <button
              onClick={() => setPage(totalPages)}
              disabled={page >= totalPages}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Ultima
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Table row + expandable detail ─────────────────────────────────────

function TableRowGroup({
  item,
  isExpanded,
  onToggle,
}: {
  item: CnpjCacheItem
  isExpanded: boolean
  onToggle: (cnpj: string) => void
}) {
  return (
    <>
      <tr
        onClick={() => onToggle(item.cnpj)}
        className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <td className="px-3 py-3">
          {isExpanded ? (
            <ChevronUpIcon className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronDownIcon className="h-4 w-4 text-gray-400" />
          )}
        </td>
        <td className="px-4 py-3 text-sm font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">
          {formatCnpj(item.cnpj)}
        </td>
        <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-white max-w-[250px] truncate" title={item.razao_social || ''}>
          {item.razao_social || '-'}
        </td>
        <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 max-w-[200px] truncate hidden lg:table-cell" title={item.nome_fantasia || ''}>
          {item.nome_fantasia || '-'}
        </td>
        <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap hidden md:table-cell">
          {item.municipio ? `${item.municipio}/${item.uf}` : '-'}
        </td>
        <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 max-w-[200px] truncate hidden xl:table-cell" title={item.cnae_fiscal_descricao || ''}>
          {item.cnae_fiscal_descricao || '-'}
        </td>
        <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap hidden xl:table-cell">
          {item.porte || '-'}
        </td>
        <td className="px-4 py-3">
          <SituacaoBadge situacao={item.situacao_cadastral} />
        </td>
      </tr>
      {isExpanded && <ExpandedRow cnpj={item.cnpj} />}
    </>
  )
}
