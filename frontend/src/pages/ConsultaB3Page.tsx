import { useState, useEffect, useCallback, useMemo, memo, Fragment } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { b3Api } from '@/services/api'
import type {
  FiltroB3,
  ConsultaB3Response,
  ClienteB3,
  OpcoesFiltrosB3,
  ConsultaSalva,
  MatchSummary,
  BdgdClienteComMatch,
  MatchItem,
  ListaProspeccao,
} from '@/types'
import toast from 'react-hot-toast'
import {
  MagnifyingGlassIcon,
  ArrowDownTrayIcon,
  FunnelIcon,
  XMarkIcon,
  MapPinIcon,
  BookmarkIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  PhoneIcon,
  EnvelopeIcon,
  LinkIcon,
  BuildingOffice2Icon,
  WrenchScrewdriverIcon,
  ListBulletIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
} from '@heroicons/react/24/solid'
import clsx from 'clsx'
import { useDebounce } from '@/hooks/usePerformance'
import { TableSkeleton, MapSkeleton } from '@/components/Skeleton'

// Custom Leaflet icons
const createCustomIcon = (color: string) =>
  L.divIcon({
    className: 'custom-marker',
    html: `<div style="
    width: 24px;
    height: 24px;
    background-color: ${color};
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  "></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  })

const solarIcon = createCustomIcon('#22c55e')
const normalIcon = createCustomIcon('#3b82f6')

function formatCnpj(cnpj: string): string {
  if (!cnpj || cnpj.length !== 14) return cnpj || ''
  return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8, 12)}-${cnpj.slice(12)}`
}

function formatPhone(phone: string | null | undefined): string {
  if (!phone) return ''
  const digits = phone.replace(/\D/g, '')
  if (digits.length === 11) return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`
  if (digits.length === 10) return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`
  return phone
}

function ScoreBadgeMini({ score }: { score: number }) {
  if (score >= 75)
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-green-100 dark:bg-green-900/30 px-1.5 py-0.5 text-[10px] font-medium text-green-800 dark:text-green-300">
        <CheckCircleIcon className="h-3 w-3" />
        {score.toFixed(0)}
      </span>
    )
  if (score >= 50)
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 px-1.5 py-0.5 text-[10px] font-medium text-yellow-800 dark:text-yellow-300">
        <ExclamationTriangleIcon className="h-3 w-3" />
        {score.toFixed(0)}
      </span>
    )
  return (
    <span className="inline-flex items-center gap-0.5 rounded-full bg-red-100 dark:bg-red-900/30 px-1.5 py-0.5 text-[10px] font-medium text-red-800 dark:text-red-300">
      <XCircleIcon className="h-3 w-3" />
      {score.toFixed(0)}
    </span>
  )
}

function ScoreBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = max > 0 ? (score / max) * 100 : 0
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 text-gray-500 dark:text-gray-400 text-right">{label}</span>
      <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-gray-600 dark:text-gray-300 text-right font-mono">
        {score.toFixed(0)}/{max}
      </span>
    </div>
  )
}

const getStreetViewUrl = (lat: number, lng: number) =>
  `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}&heading=0&pitch=0&fov=90`

// Monthly consumption chart
function MonthlyConsumptionChart({ cliente }: { cliente: ClienteB3 }) {
  const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
  const eneValues = [
    cliente.ene_01,
    cliente.ene_02,
    cliente.ene_03,
    cliente.ene_04,
    cliente.ene_05,
    cliente.ene_06,
    cliente.ene_07,
    cliente.ene_08,
    cliente.ene_09,
    cliente.ene_10,
    cliente.ene_11,
    cliente.ene_12,
  ]

  const numericValues = eneValues.map((v) => (v != null ? v : 0))
  const maxEne = Math.max(...numericValues)

  if (maxEne === 0) return null

  return (
    <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
      <h4 className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-3">
        Consumo Mensal (kWh)
      </h4>
      <div className="flex items-end gap-1 h-20">
        {numericValues.map((val, idx) => {
          const heightPct = maxEne > 0 ? (val / maxEne) * 100 : 0
          return (
            <div key={idx} className="flex flex-col items-center flex-1 gap-0.5">
              <div
                className="w-full bg-blue-500 dark:bg-blue-400 rounded-t transition-all"
                style={{ height: `${heightPct}%`, minHeight: val > 0 ? '2px' : '0' }}
                title={`${meses[idx]}: ${val.toLocaleString('pt-BR')} kWh`}
              />
              <span className="text-[8px] text-gray-500 dark:text-gray-400 leading-none">
                {meses[idx]}
              </span>
            </div>
          )
        })}
      </div>
      <div className="flex justify-between mt-1 text-[10px] text-gray-400 dark:text-gray-500">
        <span>0</span>
        <span>{maxEne.toLocaleString('pt-BR')} kWh</span>
      </div>
    </div>
  )
}

// Mobile card component
const MobileCard = memo(
  ({ cliente, matchInfo }: { cliente: ClienteB3; matchInfo?: MatchSummary }) => {
    const hasCoords = cliente.latitude && cliente.longitude

    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 space-y-3 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">
              {cliente.nome_municipio || cliente.mun || 'Cliente'}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">{cliente.nome_uf || '-'}</p>
          </div>
          <span
            className={clsx(
              'px-2 py-1 rounded-full text-xs font-medium',
              cliente.possui_solar
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
            )}
          >
            {cliente.possui_solar ? '☀️ Solar' : 'Sem Solar'}
          </span>
        </div>

        {/* GD Real Info (when available) */}
        {cliente.nome_real && (
          <div className="bg-emerald-50 dark:bg-emerald-900/20 rounded-lg p-2.5 space-y-1 border border-emerald-200 dark:border-emerald-800">
            <div className="flex items-center justify-between">
              {cliente.cnpj_real && <span className="text-xs font-mono text-emerald-700 dark:text-emerald-300">{formatCnpj(cliente.cnpj_real)}</span>}
              <span className="inline-flex items-center rounded-full bg-emerald-100 dark:bg-emerald-900/30 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800 dark:text-emerald-300">GD</span>
            </div>
            <p className="text-xs font-semibold text-emerald-800 dark:text-emerald-200 truncate">{cliente.nome_real}</p>
            {cliente.geracao_distribuida && (
              <p className="text-[10px] text-emerald-600 dark:text-emerald-400">
                {cliente.geracao_distribuida.tipo_geracao} - {cliente.geracao_distribuida.potencia_instalada_kw?.toLocaleString('pt-BR')} kW - {cliente.geracao_distribuida.porte}
              </p>
            )}
          </div>
        )}

        {/* CNPJ Match Info (fallback when no GD) */}
        {!cliente.nome_real && matchInfo && (
          <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-2.5 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-purple-700 dark:text-purple-300">
                {formatCnpj(matchInfo.cnpj)}
              </span>
              <ScoreBadgeMini score={matchInfo.score_total} />
            </div>
            <p className="text-xs font-medium text-gray-900 dark:text-white truncate">
              {matchInfo.razao_social}
            </p>
            {matchInfo.telefone && (
              <a
                href={`https://wa.me/55${matchInfo.telefone.replace(/\D/g, '')}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-green-600 dark:text-green-400"
              >
                {formatPhone(matchInfo.telefone)}
              </a>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-2">
            <span className="text-gray-500 dark:text-gray-400 text-xs">Classe</span>
            <p className="font-medium text-gray-900 dark:text-white truncate">
              {cliente.clas_sub_descricao || cliente.clas_sub || '-'}
            </p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-2">
            <span className="text-gray-500 dark:text-gray-400 text-xs">Grupo</span>
            <p className="font-medium text-gray-900 dark:text-white">{cliente.gru_tar || '-'}</p>
          </div>
          <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-2">
            <span className="text-gray-500 dark:text-gray-400 text-xs">Cons. Médio</span>
            <p className="font-semibold text-green-700 dark:text-green-400">
              {cliente.consumo_medio?.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) || '-'} kWh
            </p>
          </div>
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-2">
            <span className="text-gray-500 dark:text-gray-400 text-xs">Cons. Anual</span>
            <p className="font-semibold text-blue-700 dark:text-blue-400">
              {cliente.consumo_anual?.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) || '-'} kWh
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <span
            className={clsx(
              'flex-1 text-center px-3 py-1.5 rounded-lg text-xs font-medium',
              'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
            )}
          >
            Fase: {cliente.fas_con || '-'}
          </span>
          {hasCoords && (
            <a
              href={getStreetViewUrl(Number(cliente.latitude), Number(cliente.longitude))}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 text-center px-3 py-1.5 bg-blue-100 hover:bg-blue-200 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-400 font-semibold rounded-lg text-xs transition-colors"
            >
              🚶 Street View
            </a>
          )}
        </div>
      </div>
    )
  }
)
MobileCard.displayName = 'MobileCard'

export default function ConsultaB3Page() {
  const [showFilters, setShowFilters] = useState(true)
  const [resultados, setResultados] = useState<ConsultaB3Response | null>(null)
  const [selectedUf, setSelectedUf] = useState('')
  const [selectedMunicipios, setSelectedMunicipios] = useState<string[]>([])
  const [selectedClasses, setSelectedClasses] = useState<string[]>([])
  const [selectedGrupos, setSelectedGrupos] = useState<string[]>([])
  const [selectedFaseCon, setSelectedFaseCon] = useState('')
  const [selectedSitAtiv, setSelectedSitAtiv] = useState('')
  const [selectedAreaLoc, setSelectedAreaLoc] = useState('')
  const [solarFilter, setSolarFilter] = useState({ com: false, sem: false })

  // Text filters
  const [cnaeFilter, setCnaeFilter] = useState('')
  const [cepFilter, setCepFilter] = useState('')
  const [bairroFilter, setBairroFilter] = useState('')
  const [logradouroFilter, setLogradouroFilter] = useState('')

  // Range filters
  const [consumoMedioMin, setConsumoMedioMin] = useState('')
  const [consumoMedioMax, setConsumoMedioMax] = useState('')
  const [consumoAnualMin, setConsumoAnualMin] = useState('')
  const [consumoAnualMax, setConsumoAnualMax] = useState('')
  const [carInstMin, setCarInstMin] = useState('')
  const [carInstMax, setCarInstMax] = useState('')
  const [dicAnualMin, setDicAnualMin] = useState('')
  const [dicAnualMax, setDicAnualMax] = useState('')
  const [ficAnualMin, setFicAnualMin] = useState('')
  const [ficAnualMax, setFicAnualMax] = useState('')

  // Saved queries state
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [showSavedQueries, setShowSavedQueries] = useState(false)
  const [queryName, setQueryName] = useState('')
  const [queryDescription, setQueryDescription] = useState('')

  // CNPJ Matching states
  const [matchMap, setMatchMap] = useState<Record<string, MatchSummary>>({})
  const [matchLoading, setMatchLoading] = useState(false)
  const [expandedCodId, setExpandedCodId] = useState<string | null>(null)
  const [expandedMatches, setExpandedMatches] = useState<MatchItem[] | null>(null)
  const [expandedLoading, setExpandedLoading] = useState(false)
  const [tecnicoExpandedIds, setTecnicoExpandedIds] = useState<Set<string>>(new Set())
  const [refining, setRefining] = useState(false)
  const [refineResult, setRefineResult] = useState<{
    refined: number
    geocoded: number
    improved: number
  } | null>(null)
  const [refiningCodId, setRefiningCodId] = useState<string | null>(null)

  // Selection state for prospection lists
  const [selectedCodIds, setSelectedCodIds] = useState<Set<string>>(new Set())
  const [showListasModal, setShowListasModal] = useState(false)
  const [novaListaNome, setNovaListaNome] = useState('')
  const [novaListaDescricao, setNovaListaDescricao] = useState('')
  const [listasLoading, setListasLoading] = useState(false)
  const [listas, setListas] = useState<ListaProspeccao[]>([])
  const [addingToListaId, setAddingToListaId] = useState<number | null>(null)
  const [creatingLista, setCreatingLista] = useState(false)

  // Search debounce states
  const [searchMunicipio, setSearchMunicipio] = useState('')
  const [searchClasse, setSearchClasse] = useState('')
  const [searchGrupo, setSearchGrupo] = useState('')

  const debouncedSearchMunicipio = useDebounce(searchMunicipio, 200)
  const debouncedSearchClasse = useDebounce(searchClasse, 200)
  const debouncedSearchGrupo = useDebounce(searchGrupo, 200)

  // Valid points for map
  const pontosValidos = useMemo(() => {
    if (!resultados?.dados) return []
    return resultados.dados.filter((c) => c.latitude && c.longitude)
  }, [resultados])

  const { register, handleSubmit, reset, getValues } = useForm<FiltroB3>({
    defaultValues: {
      page: 1,
      per_page: 100,
    },
  })

  const { data: opcoesFiltros } = useQuery<OpcoesFiltrosB3>({
    queryKey: ['opcoes-filtros-b3'],
    queryFn: b3Api.opcoesFiltros,
  })

  const { data: consultasSalvas, refetch: refetchSalvas } = useQuery<ConsultaSalva[]>({
    queryKey: ['consultas-salvas', 'b3'],
    queryFn: b3Api.listarConsultasSalvas,
  })

  const salvarConsultaMutation = useMutation({
    mutationFn: b3Api.salvarConsulta,
    onSuccess: () => {
      toast.success('Consulta salva com sucesso!')
      setShowSaveModal(false)
      setQueryName('')
      setQueryDescription('')
      refetchSalvas()
    },
    onError: () => toast.error('Erro ao salvar consulta'),
  })

  const excluirConsultaMutation = useMutation({
    mutationFn: b3Api.excluirConsultaSalva,
    onSuccess: () => {
      toast.success('Consulta excluida!')
      refetchSalvas()
    },
    onError: () => toast.error('Erro ao excluir'),
  })

  const buildFiltros = (): FiltroB3 => {
    const valores = getValues()
    const filtros: FiltroB3 = {
      ...valores,
      uf: selectedUf || undefined,
      municipios: selectedMunicipios.length ? selectedMunicipios : undefined,
      classes_cliente: selectedClasses.length ? selectedClasses : undefined,
      grupos_tarifarios: selectedGrupos.length ? selectedGrupos : undefined,
      fas_con: selectedFaseCon || undefined,
      sit_ativ: selectedSitAtiv || undefined,
      area_loc: selectedAreaLoc || undefined,
      possui_solar: solarFilter.com && !solarFilter.sem ? true : !solarFilter.com && solarFilter.sem ? false : undefined,
      cnae: cnaeFilter.trim() || undefined,
      cep: cepFilter.trim() || undefined,
      bairro: bairroFilter.trim() || undefined,
      logradouro: logradouroFilter.trim() || undefined,
      consumo_medio_min: consumoMedioMin !== '' ? Number(consumoMedioMin) : undefined,
      consumo_medio_max: consumoMedioMax !== '' ? Number(consumoMedioMax) : undefined,
      consumo_anual_min: consumoAnualMin !== '' ? Number(consumoAnualMin) : undefined,
      consumo_anual_max: consumoAnualMax !== '' ? Number(consumoAnualMax) : undefined,
      car_inst_min: carInstMin !== '' ? Number(carInstMin) : undefined,
      car_inst_max: carInstMax !== '' ? Number(carInstMax) : undefined,
      dic_anual_min: dicAnualMin !== '' ? Number(dicAnualMin) : undefined,
      dic_anual_max: dicAnualMax !== '' ? Number(dicAnualMax) : undefined,
      fic_anual_min: ficAnualMin !== '' ? Number(ficAnualMin) : undefined,
      fic_anual_max: ficAnualMax !== '' ? Number(ficAnualMax) : undefined,
    }
    return filtros
  }

  const consultaMutation = useMutation({
    mutationFn: (filtros: FiltroB3) => b3Api.consulta(filtros),
    onSuccess: (data: ConsultaB3Response) => {
      setResultados(data)
      toast.success(`${data.total} registros encontrados`)
    },
    onError: () => {
      toast.error('Erro ao realizar consulta')
    },
  })

  const exportarCsvMutation = useMutation({
    mutationFn: () => b3Api.exportarCsv(buildFiltros()),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'dados_b3.csv'
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success('CSV exportado com sucesso')
    },
    onError: () => toast.error('Erro ao exportar CSV'),
  })

  const exportarXlsxMutation = useMutation({
    mutationFn: () => b3Api.exportarXlsx(buildFiltros()),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'dados_b3.xlsx'
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success('XLSX exportado com sucesso')
    },
    onError: () => toast.error('Erro ao exportar XLSX'),
  })

  const exportarKmlMutation = useMutation({
    mutationFn: () => b3Api.exportarKml(buildFiltros()),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'dados_b3.kml'
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success('KML exportado com sucesso')
    },
    onError: () => toast.error('Erro ao exportar KML'),
  })

  const onSubmit = () => {
    consultaMutation.mutate(buildFiltros())
  }

  const handleSaveQuery = () => {
    if (!queryName.trim()) {
      toast.error('Digite um nome para a consulta')
      return
    }
    salvarConsultaMutation.mutate({
      name: queryName,
      description: queryDescription,
      filters: buildFiltros(),
    })
  }

  const aplicarConsultaSalva = async (consulta: ConsultaSalva) => {
    try {
      const result = await b3Api.usarConsultaSalva(consulta.id)
      const f = result.filters as FiltroB3

      setSelectedUf(f.uf || '')
      setSelectedMunicipios((f.municipios as string[]) || [])
      setSelectedClasses((f.classes_cliente as string[]) || [])
      setSelectedGrupos((f.grupos_tarifarios as string[]) || [])
      setSelectedFaseCon((f.fas_con as string) || '')
      setSelectedSitAtiv((f.sit_ativ as string) || '')
      setSelectedAreaLoc((f.area_loc as string) || '')
      if (f.possui_solar === true) {
        setSolarFilter({ com: true, sem: false })
      } else if (f.possui_solar === false) {
        setSolarFilter({ com: false, sem: true })
      } else {
        setSolarFilter({ com: false, sem: false })
      }
      setCnaeFilter((f.cnae as string) || '')
      setCepFilter((f.cep as string) || '')
      setBairroFilter((f.bairro as string) || '')
      setLogradouroFilter((f.logradouro as string) || '')
      setConsumoMedioMin(f.consumo_medio_min != null ? String(f.consumo_medio_min) : '')
      setConsumoMedioMax(f.consumo_medio_max != null ? String(f.consumo_medio_max) : '')
      setConsumoAnualMin(f.consumo_anual_min != null ? String(f.consumo_anual_min) : '')
      setConsumoAnualMax(f.consumo_anual_max != null ? String(f.consumo_anual_max) : '')
      setCarInstMin(f.car_inst_min != null ? String(f.car_inst_min) : '')
      setCarInstMax(f.car_inst_max != null ? String(f.car_inst_max) : '')
      setDicAnualMin(f.dic_anual_min != null ? String(f.dic_anual_min) : '')
      setDicAnualMax(f.dic_anual_max != null ? String(f.dic_anual_max) : '')
      setFicAnualMin(f.fic_anual_min != null ? String(f.fic_anual_min) : '')
      setFicAnualMax(f.fic_anual_max != null ? String(f.fic_anual_max) : '')

      setShowSavedQueries(false)
      toast.success(`Consulta "${consulta.name}" carregada`)

      consultaMutation.mutate(f)
    } catch {
      toast.error('Erro ao carregar consulta')
    }
  }

  const handleReset = () => {
    reset()
    setSelectedUf('')
    setSelectedMunicipios([])
    setSelectedClasses([])
    setSelectedGrupos([])
    setSelectedFaseCon('')
    setSelectedSitAtiv('')
    setSelectedAreaLoc('')
    setSolarFilter({ com: false, sem: false })
    setCnaeFilter('')
    setCepFilter('')
    setBairroFilter('')
    setLogradouroFilter('')
    setConsumoMedioMin('')
    setConsumoMedioMax('')
    setConsumoAnualMin('')
    setConsumoAnualMax('')
    setCarInstMin('')
    setCarInstMax('')
    setDicAnualMin('')
    setDicAnualMax('')
    setFicAnualMin('')
    setFicAnualMax('')
    setSearchMunicipio('')
    setSearchClasse('')
    setSearchGrupo('')
  }

  const municipiosOptions =
    selectedUf && opcoesFiltros?.municipios_por_uf?.[selectedUf]
      ? opcoesFiltros.municipios_por_uf[selectedUf]
      : []

  const filteredMunicipios = useMemo(() => {
    if (!debouncedSearchMunicipio.trim()) return municipiosOptions.slice(0, 100)
    const search = debouncedSearchMunicipio.toLowerCase()
    return municipiosOptions.filter((m) => m.toLowerCase().includes(search)).slice(0, 100)
  }, [municipiosOptions, debouncedSearchMunicipio])

  const filteredClasses = useMemo(() => {
    const classes = opcoesFiltros?.classes_cliente || []
    if (!debouncedSearchClasse.trim()) return classes
    const search = debouncedSearchClasse.toLowerCase()
    return classes.filter((c) => c.toLowerCase().includes(search))
  }, [opcoesFiltros?.classes_cliente, debouncedSearchClasse])

  const filteredGrupos = useMemo(() => {
    const grupos = opcoesFiltros?.grupos_tarifarios || []
    if (!debouncedSearchGrupo.trim()) return grupos
    const search = debouncedSearchGrupo.toLowerCase()
    return grupos.filter((g) => g.toLowerCase().includes(search))
  }, [opcoesFiltros?.grupos_tarifarios, debouncedSearchGrupo])

  const mapCenter = useMemo(() => {
    if (pontosValidos.length === 0) return { lat: -15.7801, lng: -47.9292 }
    const lats = pontosValidos.map((c) => Number(c.latitude))
    const lngs = pontosValidos.map((c) => Number(c.longitude))
    return {
      lat: lats.reduce((a, b) => a + b, 0) / lats.length,
      lng: lngs.reduce((a, b) => a + b, 0) / lngs.length,
    }
  }, [pontosValidos])

  // Batch lookup for CNPJ matching when results change (skip clients with GD data)
  useEffect(() => {
    if (!resultados?.dados?.length) {
      setMatchMap({})
      return
    }
    const codIds = resultados.dados
      .filter((c) => c.cod_id && !c.nome_real)
      .map((c) => c.cod_id) as string[]
    if (codIds.length === 0) return
    setMatchLoading(true)
    b3Api
      .batchLookup(codIds)
      .then((data) => setMatchMap(data || {}))
      .catch(() => setMatchMap({}))
      .finally(() => setMatchLoading(false))
  }, [resultados])

  // Expand row: load all matches for a client
  const handleExpandRow = useCallback(
    async (codId: string) => {
      if (expandedCodId === codId) {
        setExpandedCodId(null)
        setExpandedMatches(null)
        return
      }
      setExpandedCodId(codId)
      setExpandedMatches(null)
      setExpandedLoading(true)
      try {
        const data: BdgdClienteComMatch = await b3Api.getClienteMatches(codId)
        setExpandedMatches(data.matches || [])
      } catch {
        setExpandedMatches([])
      } finally {
        setExpandedLoading(false)
      }
    },
    [expandedCodId]
  )

  // Refine page matches (max 100)
  const handleRefinePage = useCallback(async () => {
    if (!resultados?.dados?.length || refining) return
    const codIds = resultados.dados.map((c) => c.cod_id).filter(Boolean) as string[]
    const batch = codIds.slice(0, 100)
    setRefining(true)
    setRefineResult(null)
    try {
      const result = await b3Api.refineMatches(batch)
      setRefineResult(result)
      const data = await b3Api.batchLookup(codIds)
      setMatchMap(data || {})
    } catch {
      setRefineResult({ refined: 0, geocoded: 0, improved: -1 })
    } finally {
      setRefining(false)
    }
  }, [resultados, refining])

  // Refine a single client
  const handleRefineOne = useCallback(
    async (codId: string) => {
      setRefiningCodId(codId)
      try {
        await b3Api.refineMatches([codId])
        const data = await b3Api.batchLookup([codId])
        setMatchMap((prev) => ({ ...prev, ...data }))
        if (expandedCodId === codId) {
          const detail: BdgdClienteComMatch = await b3Api.getClienteMatches(codId)
          setExpandedMatches(detail.matches || [])
        }
        toast.success('Match refinado com sucesso!')
      } catch {
        toast.error('Erro ao refinar match')
      } finally {
        setRefiningCodId(null)
      }
    },
    [expandedCodId]
  )

  // Selection helpers
  const toggleSelectCodId = useCallback((codId: string) => {
    setSelectedCodIds((prev) => {
      const next = new Set(prev)
      if (next.has(codId)) next.delete(codId)
      else next.add(codId)
      return next
    })
  }, [])

  const toggleSelectAllOnPage = useCallback(() => {
    if (!resultados?.dados) return
    const pageIds = resultados.dados.map((c) => c.cod_id).filter(Boolean) as string[]
    const allSelected = pageIds.every((id) => selectedCodIds.has(id))
    if (allSelected) {
      setSelectedCodIds((prev) => {
        const next = new Set(prev)
        pageIds.forEach((id) => next.delete(id))
        return next
      })
    } else {
      setSelectedCodIds((prev) => {
        const next = new Set(prev)
        pageIds.forEach((id) => next.add(id))
        return next
      })
    }
  }, [resultados, selectedCodIds])

  const allOnPageSelected = useMemo(() => {
    if (!resultados?.dados?.length) return false
    const pageIds = resultados.dados.map((c) => c.cod_id).filter(Boolean) as string[]
    return pageIds.length > 0 && pageIds.every((id) => selectedCodIds.has(id))
  }, [resultados, selectedCodIds])

  // Lists handlers
  const fetchListas = useCallback(async () => {
    setListasLoading(true)
    try {
      const data = await b3Api.listarListas()
      setListas(data || [])
    } catch {
      toast.error('Erro ao carregar listas')
    } finally {
      setListasLoading(false)
    }
  }, [])

  const handleOpenListasModal = useCallback(() => {
    setShowListasModal(true)
    fetchListas()
  }, [fetchListas])

  const handleAddToLista = useCallback(
    async (listaId: number) => {
      const codIds = Array.from(selectedCodIds)
      if (codIds.length === 0) return
      setAddingToListaId(listaId)
      try {
        await b3Api.adicionarUnidadesLista(listaId, codIds)
        toast.success(`${codIds.length} UC(s) adicionadas a lista!`)
        fetchListas()
      } catch {
        toast.error('Erro ao adicionar UCs a lista')
      } finally {
        setAddingToListaId(null)
      }
    },
    [selectedCodIds, fetchListas]
  )

  const handleCreateAndAdd = useCallback(async () => {
    if (!novaListaNome.trim()) {
      toast.error('Digite um nome para a lista')
      return
    }
    const codIds = Array.from(selectedCodIds)
    setCreatingLista(true)
    try {
      if (codIds.length > 0) {
        await b3Api.salvarFiltroComoLista({
          nome: novaListaNome.trim(),
          descricao: novaListaDescricao.trim() || undefined,
          cod_ids: codIds,
        })
        toast.success(`Lista "${novaListaNome}" criada com ${codIds.length} UC(s)!`)
      } else {
        await b3Api.criarLista({
          nome: novaListaNome.trim(),
          descricao: novaListaDescricao.trim() || undefined,
        })
        toast.success(`Lista "${novaListaNome}" criada!`)
      }
      setNovaListaNome('')
      setNovaListaDescricao('')
      fetchListas()
    } catch {
      toast.error('Erro ao criar lista')
    } finally {
      setCreatingLista(false)
    }
  }, [novaListaNome, novaListaDescricao, selectedCodIds, fetchListas])

  const handleDeleteLista = useCallback(
    async (listaId: number) => {
      try {
        await b3Api.excluirLista(listaId)
        toast.success('Lista excluida!')
        fetchListas()
      } catch {
        toast.error('Erro ao excluir lista')
      }
    },
    [fetchListas]
  )

  const handleExportListaCsv = useCallback(async (listaId: number) => {
    try {
      const blob = await b3Api.exportarListaCsv(listaId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `lista_prospeccao_${listaId}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success('CSV exportado!')
    } catch {
      toast.error('Erro ao exportar CSV')
    }
  }, [])

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-teal-700 via-teal-600 to-cyan-500 text-white p-6 md:p-8">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight">⚡ Consulta BDGD B3</h1>
            <p className="text-lg md:text-xl text-white/90 mt-2 font-medium">
              Base de Dados - Baixa Tensao (BT)
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setShowSavedQueries(true)}
              className="btn-outline bg-white/10 border-white/20 text-white hover:bg-white/20 px-4 py-2"
            >
              <BookmarkIcon className="w-5 h-5" />
              <span className="ml-2 font-semibold">📂 Consultas Salvas</span>
            </button>
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className="btn-outline bg-white/10 border-white/20 text-white hover:bg-white/20 px-4 py-2"
            >
              {showFilters ? (
                <XMarkIcon className="w-5 h-5" />
              ) : (
                <FunnelIcon className="w-5 h-5" />
              )}
              <span className="ml-2 font-semibold">
                {showFilters ? 'Ocultar Filtros' : 'Mostrar Filtros'}
              </span>
            </button>
          </div>
        </div>
        <div className="absolute -right-8 -top-8 h-40 w-40 rounded-full bg-white/10" />
        <div className="absolute -left-10 -bottom-10 h-48 w-48 rounded-full bg-white/10" />
      </div>

      {/* Filters */}
      {showFilters && (
        <form onSubmit={handleSubmit(onSubmit)} className="card p-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Column 1: Location */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                <div className="h-2 w-2 rounded-full bg-teal-500" />
                Localizacao
              </div>

              {/* UF */}
              <div>
                <label className="label">UF</label>
                <select
                  className="input"
                  value={selectedUf}
                  onChange={(e) => {
                    setSelectedUf(e.target.value)
                    setSelectedMunicipios([])
                  }}
                >
                  <option value="">Todas</option>
                  {opcoesFiltros?.ufs?.map((uf) => (
                    <option key={uf} value={uf}>
                      {uf}
                    </option>
                  ))}
                </select>
              </div>

              {/* Municipios */}
              <div>
                <label className="label">
                  Municipios
                  {selectedMunicipios.length > 0 && (
                    <span className="ml-2 text-xs text-teal-600">
                      ({selectedMunicipios.length} selecionados)
                    </span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="🔍 Buscar municipio..."
                  className="input mb-1 text-sm"
                  value={searchMunicipio}
                  onChange={(e) => setSearchMunicipio(e.target.value)}
                />
                <div className="border border-gray-300 dark:border-gray-600 rounded-lg max-h-32 overflow-y-auto bg-white dark:bg-gray-800">
                  {municipiosOptions.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Selecione uma UF primeiro</p>
                  ) : filteredMunicipios.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">
                      Nenhum resultado para "{searchMunicipio}"
                    </p>
                  ) : (
                    filteredMunicipios.map((mun) => (
                      <label
                        key={mun}
                        className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer border-b border-gray-100 dark:border-gray-700 last:border-0"
                      >
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                          checked={selectedMunicipios.includes(mun)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedMunicipios([...selectedMunicipios, mun])
                            } else {
                              setSelectedMunicipios(
                                selectedMunicipios.filter((m) => m !== mun)
                              )
                            }
                          }}
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300">{mun}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Text filters: CEP, Bairro, Logradouro, CNAE */}
              <div>
                <label className="label">CNAE</label>
                <input
                  type="text"
                  className="input"
                  placeholder="Ex: 4711301"
                  value={cnaeFilter}
                  onChange={(e) => setCnaeFilter(e.target.value)}
                />
              </div>
              <div>
                <label className="label">CEP</label>
                <input
                  type="text"
                  className="input"
                  placeholder="Ex: 01310100"
                  value={cepFilter}
                  onChange={(e) => setCepFilter(e.target.value)}
                />
              </div>
              <div>
                <label className="label">Bairro</label>
                <input
                  type="text"
                  className="input"
                  placeholder="Ex: Centro"
                  value={bairroFilter}
                  onChange={(e) => setBairroFilter(e.target.value)}
                />
              </div>
              <div>
                <label className="label">Logradouro</label>
                <input
                  type="text"
                  className="input"
                  placeholder="Ex: Av Paulista"
                  value={logradouroFilter}
                  onChange={(e) => setLogradouroFilter(e.target.value)}
                />
              </div>
            </div>

            {/* Column 2: Classification */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                <div className="h-2 w-2 rounded-full bg-cyan-500" />
                Classificacao
              </div>

              {/* Classe */}
              <div>
                <label className="label">
                  Classe do Cliente
                  {selectedClasses.length > 0 && (
                    <span className="ml-2 text-xs text-teal-600">
                      ({selectedClasses.length} selecionados)
                    </span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="🔍 Buscar classe..."
                  className="input mb-1 text-sm"
                  value={searchClasse}
                  onChange={(e) => setSearchClasse(e.target.value)}
                />
                <div className="border border-gray-300 dark:border-gray-600 rounded-lg max-h-32 overflow-y-auto bg-white dark:bg-gray-800">
                  {filteredClasses.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">
                      Nenhum resultado para "{searchClasse}"
                    </p>
                  ) : (
                    filteredClasses.map((classe) => (
                      <label
                        key={classe}
                        className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer border-b border-gray-100 dark:border-gray-700 last:border-0"
                      >
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                          checked={selectedClasses.includes(classe)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedClasses([...selectedClasses, classe])
                            } else {
                              setSelectedClasses(selectedClasses.filter((c) => c !== classe))
                            }
                          }}
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300">{classe}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Grupo Tarifario */}
              <div>
                <label className="label">
                  Grupo Tarifario
                  {selectedGrupos.length > 0 && (
                    <span className="ml-2 text-xs text-teal-600">
                      ({selectedGrupos.length} selecionados)
                    </span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="🔍 Buscar grupo..."
                  className="input mb-1 text-sm"
                  value={searchGrupo}
                  onChange={(e) => setSearchGrupo(e.target.value)}
                />
                <div className="border border-gray-300 dark:border-gray-600 rounded-lg max-h-28 overflow-y-auto bg-white dark:bg-gray-800">
                  {filteredGrupos.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">
                      Nenhum resultado para "{searchGrupo}"
                    </p>
                  ) : (
                    filteredGrupos.map((gru) => (
                      <label
                        key={gru}
                        className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer border-b border-gray-100 dark:border-gray-700 last:border-0"
                      >
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                          checked={selectedGrupos.includes(gru)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedGrupos([...selectedGrupos, gru])
                            } else {
                              setSelectedGrupos(selectedGrupos.filter((g) => g !== gru))
                            }
                          }}
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300">{gru}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>

              {/* Fase Conexao */}
              <div>
                <label className="label">Fase Conexao (FAS_CON)</label>
                <select
                  className="input"
                  value={selectedFaseCon}
                  onChange={(e) => setSelectedFaseCon(e.target.value)}
                >
                  <option value="">Todas</option>
                  {opcoesFiltros?.fases_conexao?.map((f) => (
                    <option key={f.codigo} value={f.codigo}>
                      {f.codigo} - {f.descricao}
                    </option>
                  ))}
                </select>
              </div>

              {/* Situacao */}
              <div>
                <label className="label">Situacao (SIT_ATIV)</label>
                <select
                  className="input"
                  value={selectedSitAtiv}
                  onChange={(e) => setSelectedSitAtiv(e.target.value)}
                >
                  <option value="">Todas</option>
                  {opcoesFiltros?.situacoes?.map((s) => (
                    <option key={s.codigo} value={s.codigo}>
                      {s.codigo} - {s.descricao}
                    </option>
                  ))}
                </select>
              </div>

              {/* Area */}
              <div>
                <label className="label">Area (AREA_LOC)</label>
                <select
                  className="input"
                  value={selectedAreaLoc}
                  onChange={(e) => setSelectedAreaLoc(e.target.value)}
                >
                  <option value="">Todas</option>
                  {opcoesFiltros?.areas?.map((a) => (
                    <option key={a.codigo} value={a.codigo}>
                      {a.codigo} - {a.descricao}
                    </option>
                  ))}
                </select>
              </div>

              {/* Solar */}
              <div>
                <label className="label">Geracao Solar</label>
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300"
                    checked={solarFilter.com}
                    onChange={(e) => setSolarFilter((prev) => ({ ...prev, com: e.target.checked }))}
                  />
                  Possui Solar
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 mt-1">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300"
                    checked={solarFilter.sem}
                    onChange={(e) => setSolarFilter((prev) => ({ ...prev, sem: e.target.checked }))}
                  />
                  Nao Possui
                </label>
              </div>
            </div>

            {/* Column 3: Ranges */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                <div className="h-2 w-2 rounded-full bg-teal-500" />
                Consumo e Qualidade
              </div>

              {/* Consumo Medio */}
              <div>
                <label className="label">Consumo Medio (kWh/mes)</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Min"
                    value={consumoMedioMin}
                    onChange={(e) => setConsumoMedioMin(e.target.value)}
                  />
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Max"
                    value={consumoMedioMax}
                    onChange={(e) => setConsumoMedioMax(e.target.value)}
                  />
                </div>
              </div>

              {/* Consumo Anual */}
              <div>
                <label className="label">Consumo Anual (kWh/ano)</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Min"
                    value={consumoAnualMin}
                    onChange={(e) => setConsumoAnualMin(e.target.value)}
                  />
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Max"
                    value={consumoAnualMax}
                    onChange={(e) => setConsumoAnualMax(e.target.value)}
                  />
                </div>
              </div>

              {/* Carga Instalada */}
              <div>
                <label className="label">Carga Instalada (kW)</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Min"
                    value={carInstMin}
                    onChange={(e) => setCarInstMin(e.target.value)}
                  />
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Max"
                    value={carInstMax}
                    onChange={(e) => setCarInstMax(e.target.value)}
                  />
                </div>
              </div>

              {/* DIC Anual */}
              <div>
                <label className="label">DIC Anual (h)</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Min"
                    value={dicAnualMin}
                    onChange={(e) => setDicAnualMin(e.target.value)}
                  />
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Max"
                    value={dicAnualMax}
                    onChange={(e) => setDicAnualMax(e.target.value)}
                  />
                </div>
              </div>

              {/* FIC Anual */}
              <div>
                <label className="label">FIC Anual (interrupcoes)</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Min"
                    value={ficAnualMin}
                    onChange={(e) => setFicAnualMin(e.target.value)}
                  />
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    className="input"
                    placeholder="Max"
                    value={ficAnualMax}
                    onChange={(e) => setFicAnualMax(e.target.value)}
                  />
                </div>
              </div>

              {/* Per page */}
              <div>
                <label className="label">Registros por pagina</label>
                <select className="input" {...register('per_page', { valueAsNumber: true })}>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={250}>250</option>
                  <option value={500}>500</option>
                  <option value={1000}>1000</option>
                </select>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-4 border-t dark:border-gray-700">
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
              <span className="ml-2">Buscar</span>
            </button>

            <button type="button" onClick={handleReset} className="btn-secondary">
              Limpar Filtros
            </button>

            <button
              type="button"
              onClick={() => setShowSaveModal(true)}
              className="inline-flex items-center px-4 py-2 bg-purple-100 hover:bg-purple-200 dark:bg-purple-900/30 dark:hover:bg-purple-900/50 text-purple-700 dark:text-purple-300 font-medium rounded-lg transition-colors"
            >
              <BookmarkIcon className="w-5 h-5 mr-2" />
              💾 Salvar Consulta
            </button>
          </div>
        </form>
      )}

      {/* Loading State */}
      {consultaMutation.isPending && (
        <div className="space-y-4">
          <div className="card p-5 bg-gradient-to-r from-gray-50 to-white dark:from-gray-800 dark:to-gray-700">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin"></div>
              <div>
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                  Buscando dados...
                </h2>
                <p className="text-gray-500 dark:text-gray-400">
                  Aguarde enquanto processamos sua consulta
                </p>
              </div>
            </div>
          </div>
          <div className="card">
            <TableSkeleton rows={10} cols={10} />
          </div>
          <div className="card">
            <MapSkeleton />
          </div>
        </div>
      )}

      {/* Results */}
      {resultados && !consultaMutation.isPending && (
        <div className="space-y-4">
          {/* Results header */}
          <div className="card p-5 bg-gradient-to-r from-gray-50 to-white dark:from-gray-800 dark:to-gray-700">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
              <div>
                <h2 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
                  📊 Resultados da Consulta B3
                </h2>
                <div className="flex items-center gap-3 mt-2">
                  <p className="text-lg text-gray-600 dark:text-gray-300">
                    <span className="font-bold text-2xl text-teal-600">
                      {resultados.total.toLocaleString('pt-BR')}
                    </span>{' '}
                    registros encontrados
                    <span className="text-gray-400 mx-2">•</span>
                    Pagina <span className="font-semibold">{resultados.page}</span> de{' '}
                    <span className="font-semibold">{resultados.total_pages}</span>
                  </p>
                  {resultados.dados.length > 0 && (
                    <button
                      onClick={handleRefinePage}
                      disabled={refining}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      title="Geocodifica coordenadas e re-faz matching para melhorar os scores desta pagina (max 100)"
                    >
                      <ArrowPathIcon
                        className={`h-3.5 w-3.5 ${refining ? 'animate-spin' : ''}`}
                      />
                      {refining ? 'Afinando...' : 'Afinar Busca'}
                    </button>
                  )}
                </div>
              </div>

              {/* Download buttons */}
              <div className="grid grid-cols-3 gap-2 w-full sm:w-auto sm:flex sm:flex-wrap">
                <button
                  onClick={() => exportarCsvMutation.mutate()}
                  disabled={exportarCsvMutation.isPending}
                  className="inline-flex items-center justify-center px-3 py-2 sm:px-5 sm:py-3 bg-green-600 hover:bg-green-700 text-white font-bold rounded-lg transition-colors disabled:opacity-50 text-sm sm:text-base shadow-lg hover:shadow-xl"
                >
                  {exportarCsvMutation.isPending ? (
                    <span className="spinner mr-1" />
                  ) : (
                    <ArrowDownTrayIcon className="w-4 h-4 sm:w-5 sm:h-5 mr-1 sm:mr-2" />
                  )}
                  <span className="hidden sm:inline">📥</span> CSV
                </button>
                <button
                  onClick={() => exportarXlsxMutation.mutate()}
                  disabled={exportarXlsxMutation.isPending}
                  className="inline-flex items-center justify-center px-3 py-2 sm:px-5 sm:py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg transition-colors disabled:opacity-50 text-sm sm:text-base shadow-lg hover:shadow-xl"
                >
                  {exportarXlsxMutation.isPending ? (
                    <span className="spinner mr-1" />
                  ) : (
                    <ArrowDownTrayIcon className="w-4 h-4 sm:w-5 sm:h-5 mr-1 sm:mr-2" />
                  )}
                  <span className="hidden sm:inline">📥</span> XLSX
                </button>
                <button
                  onClick={() => exportarKmlMutation.mutate()}
                  disabled={exportarKmlMutation.isPending}
                  className="inline-flex items-center justify-center px-3 py-2 sm:px-5 sm:py-3 bg-orange-600 hover:bg-orange-700 text-white font-bold rounded-lg transition-colors disabled:opacity-50 text-sm sm:text-base shadow-lg hover:shadow-xl"
                >
                  {exportarKmlMutation.isPending ? (
                    <span className="spinner mr-1" />
                  ) : (
                    <ArrowDownTrayIcon className="w-4 h-4 sm:w-5 sm:h-5 mr-1 sm:mr-2" />
                  )}
                  <span className="hidden sm:inline">📥</span> KML
                </button>
              </div>
            </div>
          </div>

          {/* Refine feedback */}
          {refineResult && (
            <div
              className={`rounded-lg p-3 text-sm ${
                refineResult.improved === -1
                  ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
                  : 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300'
              }`}
            >
              {refineResult.improved === -1 ? (
                <span>Erro ao refinar busca. Tente novamente.</span>
              ) : (
                <span>
                  Refinamento concluido: <strong>{refineResult.refined}</strong> clientes
                  processados, <strong>{refineResult.geocoded}</strong> novos enderecos
                  geocodificados, <strong>{refineResult.improved}</strong> scores melhorados.
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

          {/* Mobile cards */}
          <div className="block md:hidden space-y-3">
            {resultados.dados.map((cliente, idx) => {
              const mCodId = cliente.cod_id
              return (
                <div key={mCodId || idx} className="relative">
                  {mCodId && (
                    <div className="absolute top-3 right-3 z-10">
                      <input
                        type="checkbox"
                        className="h-5 w-5 rounded border-gray-300 dark:border-gray-600 text-teal-600 focus:ring-teal-500 cursor-pointer"
                        checked={selectedCodIds.has(mCodId)}
                        onChange={() => toggleSelectCodId(mCodId)}
                      />
                    </div>
                  )}
                  <MobileCard
                    cliente={cliente}
                    matchInfo={mCodId ? matchMap[mCodId] : undefined}
                  />
                </div>
              )
            })}
          </div>

          {/* Desktop table */}
          <div className="hidden md:block card">
            <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
              <table className="w-full text-sm min-w-[1200px]">
                <thead className="bg-gray-100 dark:bg-gray-900 border-y border-gray-200 dark:border-gray-700 sticky top-0 z-10">
                  <tr>
                    <th className="px-1 py-2 w-8">
                      <input
                        type="checkbox"
                        className="rounded border-gray-300 dark:border-gray-600 text-teal-600 focus:ring-teal-500 cursor-pointer"
                        checked={allOnPageSelected}
                        onChange={(e) => {
                          e.stopPropagation()
                          toggleSelectAllOnPage()
                        }}
                        title="Selecionar todos da pagina"
                      />
                    </th>
                    <th className="px-1 py-2 w-6"></th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      UF
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Municipio
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Classe
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      CNAE
                    </th>
                    <th className="px-2 py-2 text-center text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Fase
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Grupo Tar
                    </th>
                    <th className="px-2 py-2 text-right text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Cons. Medio (kWh)
                    </th>
                    <th className="px-2 py-2 text-right text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Cons. Anual (kWh)
                    </th>
                    <th className="px-2 py-2 text-right text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Carga Inst (kW)
                    </th>
                    <th className="px-2 py-2 text-right text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      DIC
                    </th>
                    <th className="px-2 py-2 text-right text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      FIC
                    </th>
                    <th className="px-2 py-2 text-center text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Solar
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-purple-700 dark:text-purple-300 uppercase whitespace-nowrap">
                      CNPJ
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-purple-700 dark:text-purple-300 uppercase whitespace-nowrap">
                      Empresa
                    </th>
                    <th className="px-2 py-2 text-center text-xs font-bold text-purple-700 dark:text-purple-300 uppercase whitespace-nowrap">
                      Score
                    </th>
                    <th className="px-2 py-2 text-center text-xs font-bold text-gray-700 dark:text-gray-300 uppercase whitespace-nowrap">
                      Acoes
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                  {resultados.dados.map((cliente, idx) => {
                    const codId = cliente.cod_id
                    const mi = codId ? matchMap[codId] : undefined
                    const isExpanded = expandedCodId === codId
                    const hasCoords = cliente.latitude && cliente.longitude

                    return (
                      <Fragment key={codId || idx}>
                        <tr
                          className={clsx(
                            'hover:bg-teal-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer',
                            isExpanded && 'bg-teal-50 dark:bg-gray-700/50',
                            codId && selectedCodIds.has(codId) && 'bg-teal-50/70 dark:bg-teal-900/20'
                          )}
                          onClick={() => codId && handleExpandRow(codId)}
                        >
                          <td className="px-1 py-1.5 text-center">
                            {codId && (
                              <input
                                type="checkbox"
                                className="rounded border-gray-300 dark:border-gray-600 text-teal-600 focus:ring-teal-500 cursor-pointer"
                                checked={selectedCodIds.has(codId)}
                                onChange={(e) => {
                                  e.stopPropagation()
                                  toggleSelectCodId(codId)
                                }}
                                onClick={(e) => e.stopPropagation()}
                              />
                            )}
                          </td>
                          <td className="px-1 py-1.5 text-center">
                            {isExpanded ? (
                              <ChevronUpIcon className="h-4 w-4 text-gray-400" />
                            ) : (
                              <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                            )}
                          </td>
                          <td className="px-2 py-1.5 text-xs font-semibold text-gray-900 dark:text-white whitespace-nowrap">
                            {cliente.nome_uf || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-gray-800 dark:text-gray-200 whitespace-nowrap">
                            {cliente.nome_municipio || cliente.mun || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-gray-600 dark:text-gray-300 max-w-[120px] truncate">
                            {cliente.clas_sub_descricao || cliente.clas_sub || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs font-mono text-gray-600 dark:text-gray-300 whitespace-nowrap">
                            {cliente.cnae || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-center whitespace-nowrap">
                            <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                              {cliente.fas_con || '-'}
                            </span>
                          </td>
                          <td className="px-2 py-1.5 text-xs text-gray-600 dark:text-gray-300 font-medium whitespace-nowrap">
                            {cliente.gru_tar || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-right font-mono font-semibold text-green-700 dark:text-green-400 whitespace-nowrap">
                            {cliente.consumo_medio?.toLocaleString('pt-BR', {
                              maximumFractionDigits: 1,
                            }) || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-right font-mono font-semibold text-blue-700 dark:text-blue-400 whitespace-nowrap">
                            {cliente.consumo_anual?.toLocaleString('pt-BR', {
                              maximumFractionDigits: 0,
                            }) || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-right font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {cliente.car_inst?.toLocaleString('pt-BR', {
                              maximumFractionDigits: 1,
                            }) || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-right font-mono text-orange-600 dark:text-orange-400 whitespace-nowrap">
                            {cliente.dic_anual?.toLocaleString('pt-BR', {
                              maximumFractionDigits: 2,
                            }) || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-right font-mono text-orange-600 dark:text-orange-400 whitespace-nowrap">
                            {cliente.fic_anual?.toLocaleString('pt-BR', {
                              maximumFractionDigits: 2,
                            }) || '-'}
                          </td>
                          <td className="px-2 py-1.5 text-center">
                            <span
                              className={clsx(
                                'inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold',
                                cliente.possui_solar
                                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                                  : 'bg-red-50 text-red-400 dark:bg-red-900/20 dark:text-red-400'
                              )}
                            >
                              {cliente.possui_solar ? '☀️' : '—'}
                            </span>
                          </td>
                          <td className="px-2 py-1.5 text-xs font-mono whitespace-nowrap">
                            {cliente.cnpj_real ? (
                              <span className="text-emerald-700 dark:text-emerald-300" title="CNPJ confirmado via GD">{formatCnpj(cliente.cnpj_real)}</span>
                            ) : mi ? (
                              <span className="text-purple-700 dark:text-purple-300">{formatCnpj(mi.cnpj)}</span>
                            ) : matchLoading ? '...' : '—'}
                          </td>
                          <td className="px-2 py-1.5 text-xs text-gray-800 dark:text-gray-200 max-w-[160px] truncate">
                            {cliente.nome_real ? (
                              <span className="font-semibold text-emerald-700 dark:text-emerald-300" title="Nome confirmado via GD">{cliente.nome_real}</span>
                            ) : mi?.razao_social || (matchLoading ? '...' : '—')}
                          </td>
                          <td className="px-2 py-1.5 text-center">
                            {cliente.nome_real ? (
                              <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 px-1.5 py-0.5 text-[10px] font-medium text-emerald-800 dark:text-emerald-300" title="Identificado via Geração Distribuída">GD</span>
                            ) : mi ? <ScoreBadgeMini score={mi.score_total} /> : null}
                          </td>
                          <td className="px-2 py-1.5 text-center whitespace-nowrap">
                            <div className="flex items-center justify-center gap-1">
                              {hasCoords && (
                                <a
                                  href={getStreetViewUrl(
                                    Number(cliente.latitude),
                                    Number(cliente.longitude)
                                  )}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="inline-flex items-center px-1.5 py-0.5 bg-blue-100 hover:bg-blue-200 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-400 rounded text-[10px] font-medium transition-colors"
                                  title="Abrir Street View"
                                >
                                  🚶
                                </a>
                              )}
                              {mi?.telefone && (
                                <a
                                  href={`https://wa.me/55${mi.telefone.replace(/\D/g, '')}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="inline-flex items-center px-1.5 py-0.5 bg-green-100 hover:bg-green-200 dark:bg-green-900/30 dark:hover:bg-green-900/50 text-green-700 dark:text-green-400 rounded text-[10px] font-medium transition-colors"
                                  title={`WhatsApp: ${formatPhone(mi.telefone)}`}
                                >
                                  📱
                                </a>
                              )}
                            </div>
                          </td>
                        </tr>

                        {/* Expanded row */}
                        {isExpanded && codId && (
                          <tr>
                            <td
                              colSpan={18}
                              className="px-4 py-4 bg-gray-50 dark:bg-gray-900/50"
                            >
                              {expandedLoading ? (
                                <div className="text-center text-gray-500 dark:text-gray-400 py-4">
                                  Carregando detalhes...
                                </div>
                              ) : (
                                <div className="space-y-3">
                                  {/* BDGD data */}
                                  <div className="p-3 bg-teal-50 dark:bg-teal-900/20 rounded-lg">
                                    <h4 className="text-sm font-semibold text-teal-800 dark:text-teal-300 mb-2">
                                      Dados BDGD B3 do Cliente
                                    </h4>
                                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2 text-xs">
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Classe:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white">
                                          {cliente.clas_sub_descricao || cliente.clas_sub}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Grupo:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white">
                                          {cliente.gru_tar}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          CNAE:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white font-mono">
                                          {cliente.cnae || '-'}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Fase:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white">
                                          {cliente.fas_con || '-'}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Situacao:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white">
                                          {cliente.sit_ativ || '-'}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Area:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white">
                                          {cliente.area_loc || '-'}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Cons. Medio:
                                        </span>{' '}
                                        <span className="text-green-700 dark:text-green-400 font-semibold">
                                          {cliente.consumo_medio?.toLocaleString('pt-BR')} kWh/mes
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Cons. Anual:
                                        </span>{' '}
                                        <span className="text-blue-700 dark:text-blue-400 font-semibold">
                                          {cliente.consumo_anual?.toLocaleString('pt-BR')} kWh/ano
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Carga Inst:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white font-semibold">
                                          {cliente.car_inst?.toLocaleString('pt-BR')} kW
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          CEP:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white font-mono">
                                          {cliente.cep || '-'}
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          Bairro:
                                        </span>{' '}
                                        <span className="text-gray-900 dark:text-white">
                                          {cliente.brr || '-'}
                                        </span>
                                      </div>
                                      <div>
                                        {hasCoords && (
                                          <a
                                            href={getStreetViewUrl(
                                              Number(cliente.latitude),
                                              Number(cliente.longitude)
                                            )}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-blue-600 dark:text-blue-400 hover:underline"
                                          >
                                            🚶 Street View
                                          </a>
                                        )}
                                      </div>
                                    </div>
                                  </div>

                                  {/* Dados de Geração Distribuída */}
                                  {cliente.geracao_distribuida && (
                                    <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg border border-emerald-200 dark:border-emerald-800">
                                      <div className="flex items-center justify-between mb-2">
                                        <h4 className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">Geração Distribuída</h4>
                                        {cliente.geracao_distribuida.dados_tecnicos && (
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation()
                                              setTecnicoExpandedIds(prev => {
                                                const next = new Set(prev)
                                                if (next.has(codId)) next.delete(codId)
                                                else next.add(codId)
                                                return next
                                              })
                                            }}
                                            className={clsx(
                                              'inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-md transition-colors',
                                              tecnicoExpandedIds.has(codId)
                                                ? 'bg-emerald-600 text-white'
                                                : 'bg-emerald-100 dark:bg-emerald-800/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-200 dark:hover:bg-emerald-800/60'
                                            )}
                                            title="Ver detalhamento técnico da usina"
                                          >
                                            <WrenchScrewdriverIcon className="h-3.5 w-3.5" />
                                            Dados Técnicos
                                          </button>
                                        )}
                                      </div>
                                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                        {cliente.nome_real && (
                                          <div className="md:col-span-2"><span className="text-gray-500 dark:text-gray-400">Titular:</span> <span className="text-emerald-800 dark:text-emerald-200 font-semibold">{cliente.nome_real}</span></div>
                                        )}
                                        {cliente.cnpj_real && (
                                          <div><span className="text-gray-500 dark:text-gray-400">CNPJ:</span> <span className="text-emerald-700 dark:text-emerald-300 font-mono">{formatCnpj(cliente.cnpj_real)}</span></div>
                                        )}
                                        <div><span className="text-gray-500 dark:text-gray-400">Tipo:</span> <span className="text-gray-900 dark:text-white font-semibold">{cliente.geracao_distribuida.tipo_geracao || '-'}</span></div>
                                        <div><span className="text-gray-500 dark:text-gray-400">Fonte:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.fonte_geracao || '-'}</span></div>
                                        <div><span className="text-gray-500 dark:text-gray-400">Porte:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.porte || '-'}</span></div>
                                        <div><span className="text-gray-500 dark:text-gray-400">Potência:</span> <span className="text-emerald-700 dark:text-emerald-400 font-semibold">{cliente.geracao_distribuida.potencia_instalada_kw?.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} kW</span></div>
                                        <div><span className="text-gray-500 dark:text-gray-400">Módulos:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.qtd_modulos || '-'}</span></div>
                                        <div><span className="text-gray-500 dark:text-gray-400">Modalidade:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.modalidade || '-'}</span></div>
                                        {cliente.geracao_distribuida.data_conexao && (
                                          <div><span className="text-gray-500 dark:text-gray-400">Conexão:</span> <span className="text-gray-900 dark:text-white">{new Date(cliente.geracao_distribuida.data_conexao).toLocaleDateString('pt-BR')}</span></div>
                                        )}
                                      </div>
                                      {/* Dados Técnicos da Usina - Expandível */}
                                      {cliente.geracao_distribuida.dados_tecnicos && tecnicoExpandedIds.has(codId) && (
                                        <div className="mt-2 pt-2 border-t border-emerald-200 dark:border-emerald-800 animate-in fade-in slide-in-from-top-1 duration-200">
                                          <h5 className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 mb-1.5 flex items-center gap-1">
                                            <WrenchScrewdriverIcon className="h-3.5 w-3.5" />
                                            Detalhamento Técnico ({cliente.geracao_distribuida.dados_tecnicos.tipo?.toUpperCase()})
                                          </h5>
                                          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                            {cliente.geracao_distribuida.dados_tecnicos.tipo === 'solar' && (<>
                                              {cliente.geracao_distribuida.dados_tecnicos.nom_fabricante_modulo && (
                                                <div className="md:col-span-2"><span className="text-gray-500 dark:text-gray-400">Módulo:</span> <span className="text-gray-900 dark:text-white font-medium">{cliente.geracao_distribuida.dados_tecnicos.nom_fabricante_modulo} {cliente.geracao_distribuida.dados_tecnicos.nom_modelo_modulo || ''}</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.nom_fabricante_inversor && (
                                                <div className="md:col-span-2"><span className="text-gray-500 dark:text-gray-400">Inversor:</span> <span className="text-gray-900 dark:text-white font-medium">{cliente.geracao_distribuida.dados_tecnicos.nom_fabricante_inversor} {cliente.geracao_distribuida.dados_tecnicos.nom_modelo_inversor || ''}</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.mda_area_arranjo && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Área Arranjo:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.mda_area_arranjo?.toLocaleString('pt-BR')} m²</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.qtd_modulos && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Qtd Módulos:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.qtd_modulos}</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.mda_potencia_modulos && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Pot. Módulos:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.mda_potencia_modulos?.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} kW</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.mda_potencia_inversores && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Pot. Inversores:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.mda_potencia_inversores?.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} kW</span></div>
                                              )}
                                            </>)}
                                            {cliente.geracao_distribuida.dados_tecnicos.tipo === 'termica' && (<>
                                              {cliente.geracao_distribuida.dados_tecnicos.dsc_ciclo_termodinamico && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Ciclo Termodinâmico:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.dsc_ciclo_termodinamico}</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.dsc_maquina_motriz && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Máquina Motriz:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.dsc_maquina_motriz}</span></div>
                                              )}
                                            </>)}
                                            {cliente.geracao_distribuida.dados_tecnicos.tipo === 'eolica' && (<>
                                              {cliente.geracao_distribuida.dados_tecnicos.nom_fabricante_aerogerador && (
                                                <div className="md:col-span-2"><span className="text-gray-500 dark:text-gray-400">Aerogerador:</span> <span className="text-gray-900 dark:text-white font-medium">{cliente.geracao_distribuida.dados_tecnicos.nom_fabricante_aerogerador} {cliente.geracao_distribuida.dados_tecnicos.dsc_modelo_aerogerador || ''}</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.mda_altura_pa && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Altura Pá:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.mda_altura_pa} m</span></div>
                                              )}
                                            </>)}
                                            {cliente.geracao_distribuida.dados_tecnicos.tipo === 'hidraulica' && (<>
                                              {cliente.geracao_distribuida.dados_tecnicos.nom_rio && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Rio:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.nom_rio}</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.mda_potencia_aparente && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Pot. Aparente:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.mda_potencia_aparente} kVA</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.mda_fator_potencia && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Fator de Potência:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.mda_fator_potencia}</span></div>
                                              )}
                                              {cliente.geracao_distribuida.dados_tecnicos.mda_tensao && (
                                                <div><span className="text-gray-500 dark:text-gray-400">Tensão:</span> <span className="text-gray-900 dark:text-white">{cliente.geracao_distribuida.dados_tecnicos.mda_tensao} kV</span></div>
                                              )}
                                            </>)}
                                            {cliente.geracao_distribuida.dados_tecnicos.mda_potencia_instalada && (
                                              <div><span className="text-gray-500 dark:text-gray-400">Pot. Técnica:</span> <span className="text-emerald-700 dark:text-emerald-400 font-semibold">{cliente.geracao_distribuida.dados_tecnicos.mda_potencia_instalada?.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} kW</span></div>
                                            )}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  )}

                                  {/* DIC/FIC info */}
                                  <div className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                                    <h4 className="text-sm font-semibold text-orange-800 dark:text-orange-300 mb-2">
                                      Qualidade do Fornecimento
                                    </h4>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          DIC Anual:
                                        </span>{' '}
                                        <span className="text-orange-700 dark:text-orange-400 font-semibold">
                                          {cliente.dic_anual?.toLocaleString('pt-BR', {
                                            maximumFractionDigits: 2,
                                          }) || '-'}{' '}
                                          h
                                        </span>
                                      </div>
                                      <div>
                                        <span className="text-gray-500 dark:text-gray-400">
                                          FIC Anual:
                                        </span>{' '}
                                        <span className="text-orange-700 dark:text-orange-400 font-semibold">
                                          {cliente.fic_anual?.toLocaleString('pt-BR', {
                                            maximumFractionDigits: 2,
                                          }) || '-'}{' '}
                                          int.
                                        </span>
                                      </div>
                                    </div>
                                  </div>

                                  {/* Monthly consumption chart */}
                                  <MonthlyConsumptionChart cliente={cliente} />

                                  {/* Refine button */}
                                  <div className="flex items-center gap-2">
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handleRefineOne(codId)
                                      }}
                                      disabled={refiningCodId === codId}
                                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                    >
                                      <ArrowPathIcon
                                        className={`h-3.5 w-3.5 ${refiningCodId === codId ? 'animate-spin' : ''}`}
                                      />
                                      {refiningCodId === codId
                                        ? 'Afinando...'
                                        : 'Afinar este cliente'}
                                    </button>
                                  </div>

                                  {/* CNPJ match list */}
                                  {expandedMatches && expandedMatches.length > 0 ? (
                                    <div>
                                      <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                                        CNPJs Candidatos ({expandedMatches.length})
                                      </h4>
                                      <div className="space-y-2">
                                        {expandedMatches.map((match) => (
                                          <div
                                            key={`${match.cnpj}-${match.rank}`}
                                            className="border dark:border-gray-700 rounded-lg p-3 bg-white dark:bg-gray-800"
                                          >
                                            <div className="flex items-start justify-between mb-2">
                                              <div>
                                                <div className="flex items-center gap-2">
                                                  <span className="text-xs font-mono text-blue-600 dark:text-blue-400">
                                                    {formatCnpj(match.cnpj)}
                                                  </span>
                                                  <span className="text-[10px] bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded text-gray-500 dark:text-gray-400">
                                                    #{match.rank}
                                                  </span>
                                                  {match.address_source === 'geocoded' && (
                                                    <span className="inline-flex items-center gap-0.5 rounded-full bg-purple-100 dark:bg-purple-900/30 px-1.5 py-0.5 text-[10px] font-medium text-purple-800 dark:text-purple-300">
                                                      <MapPinIcon className="h-2.5 w-2.5" />
                                                      Geocode
                                                    </span>
                                                  )}
                                                </div>
                                                <p className="text-xs font-semibold text-gray-900 dark:text-white mt-0.5">
                                                  {match.razao_social}
                                                </p>
                                                {match.nome_fantasia && (
                                                  <p className="text-[10px] text-gray-500 dark:text-gray-400">
                                                    {match.nome_fantasia}
                                                  </p>
                                                )}
                                              </div>
                                              <ScoreBadgeMini score={match.score_total} />
                                            </div>
                                            <div className="space-y-0.5 mb-2">
                                              <ScoreBar
                                                label="CEP"
                                                score={match.score_cep}
                                                max={40}
                                              />
                                              <ScoreBar
                                                label="CNAE"
                                                score={match.score_cnae}
                                                max={25}
                                              />
                                              <ScoreBar
                                                label="Endereco"
                                                score={match.score_endereco}
                                                max={20}
                                              />
                                              <ScoreBar
                                                label="Numero"
                                                score={match.score_numero}
                                                max={10}
                                              />
                                              <ScoreBar
                                                label="Bairro"
                                                score={match.score_bairro}
                                                max={5}
                                              />
                                            </div>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-1 text-[11px] text-gray-600 dark:text-gray-300">
                                              <div className="flex items-center gap-1">
                                                <MapPinIcon className="h-3 w-3 text-gray-400" />
                                                {match.cnpj_logradouro}
                                                {match.cnpj_numero ? `, ${match.cnpj_numero}` : ''}
                                                {match.cnpj_bairro ? ` - ${match.cnpj_bairro}` : ''}
                                              </div>
                                              <div className="flex items-center gap-1">
                                                <BuildingOffice2Icon className="h-3 w-3 text-gray-400" />
                                                {match.cnpj_municipio}/{match.cnpj_uf}
                                                {match.cnpj_cep ? ` - CEP ${match.cnpj_cep}` : ''}
                                              </div>
                                              {match.cnpj_cnae_descricao && (
                                                <div className="flex items-center gap-1 md:col-span-2">
                                                  <LinkIcon className="h-3 w-3 text-gray-400" />
                                                  CNAE: {match.cnpj_cnae} -{' '}
                                                  {match.cnpj_cnae_descricao}
                                                </div>
                                              )}
                                              {match.cnpj_telefone && (
                                                <div className="flex items-center gap-1">
                                                  <PhoneIcon className="h-3 w-3 text-gray-400" />
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
                                                  <EnvelopeIcon className="h-3 w-3 text-gray-400" />
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
                                        ))}
                                      </div>
                                    </div>
                                  ) : expandedMatches && expandedMatches.length === 0 ? (
                                    <p className="text-xs text-gray-500 dark:text-gray-400">
                                      Nenhum match CNPJ encontrado para este cliente.
                                    </p>
                                  ) : null}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Desktop pagination */}
            <div className="px-4 py-3 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800 flex flex-col sm:flex-row items-center justify-between gap-3">
              <p className="text-sm text-gray-600 dark:text-gray-400 text-center sm:text-left">
                <span className="font-bold">
                  {(resultados.page - 1) * resultados.per_page + 1}
                </span>
                -
                <span className="font-bold">
                  {Math.min(resultados.page * resultados.per_page, resultados.total)}
                </span>{' '}
                de{' '}
                <span className="font-bold text-teal-600">
                  {resultados.total.toLocaleString('pt-BR')}
                </span>
              </p>

              <div className="flex items-center gap-2">
                <button
                  disabled={resultados.page <= 1}
                  onClick={() => {
                    const formData = buildFiltros()
                    consultaMutation.mutate({ ...formData, page: resultados.page - 1 })
                  }}
                  className="btn-outline text-sm px-4 py-2 font-semibold"
                >
                  Anterior
                </button>
                <span className="px-3 py-1 bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 font-bold rounded-lg text-sm">
                  {resultados.page} / {resultados.total_pages}
                </span>
                <button
                  disabled={resultados.page >= resultados.total_pages}
                  onClick={() => {
                    const formData = buildFiltros()
                    consultaMutation.mutate({ ...formData, page: resultados.page + 1 })
                  }}
                  className="btn-outline text-sm px-4 py-2 font-semibold"
                >
                  Proxima
                </button>
              </div>
            </div>
          </div>

          {/* Mobile pagination */}
          <div className="block md:hidden card p-4">
            <div className="flex flex-col items-center gap-3">
              <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
                <span className="font-bold">
                  {(resultados.page - 1) * resultados.per_page + 1}
                </span>
                -
                <span className="font-bold">
                  {Math.min(resultados.page * resultados.per_page, resultados.total)}
                </span>{' '}
                de{' '}
                <span className="font-bold text-teal-600">
                  {resultados.total.toLocaleString('pt-BR')}
                </span>
              </p>

              <div className="flex items-center gap-2 w-full">
                <button
                  disabled={resultados.page <= 1}
                  onClick={() => {
                    const formData = buildFiltros()
                    consultaMutation.mutate({ ...formData, page: resultados.page - 1 })
                  }}
                  className="flex-1 btn-outline text-sm px-3 py-2 font-semibold"
                >
                  Anterior
                </button>
                <span className="px-3 py-1 bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 font-bold rounded-lg text-sm">
                  {resultados.page}/{resultados.total_pages}
                </span>
                <button
                  disabled={resultados.page >= resultados.total_pages}
                  onClick={() => {
                    const formData = buildFiltros()
                    consultaMutation.mutate({ ...formData, page: resultados.page + 1 })
                  }}
                  className="flex-1 btn-outline text-sm px-3 py-2 font-semibold"
                >
                  Proxima
                </button>
              </div>
            </div>
          </div>

          {/* Map */}
          <div className="card ring-2 md:ring-4 ring-teal-200 dark:ring-teal-900/50 ring-offset-1 md:ring-offset-2 shadow-xl md:shadow-2xl">
            <div className="px-4 py-4 md:px-6 md:py-5 border-b bg-gradient-to-r from-teal-600 to-cyan-600">
              <h2 className="text-xl md:text-3xl font-bold text-white flex items-center gap-2 md:gap-3">
                <MapPinIcon className="w-6 h-6 md:w-8 md:h-8 text-white" />
                🗺️ Mapa
              </h2>
              <p className="text-sm md:text-base text-teal-100 mt-1">
                {pontosValidos.length > 0
                  ? `📍 ${pontosValidos.length} pontos • Clique para detalhes`
                  : 'Sem coordenadas validas'}
              </p>
            </div>

            <div className="relative">
              {pontosValidos.length > 0 ? (
                <MapContainer
                  center={[mapCenter.lat, mapCenter.lng]}
                  zoom={pontosValidos.length === 1 ? 14 : 5}
                  style={{ height: 'clamp(350px, 60vh, 700px)', width: '100%' }}
                  scrollWheelZoom={true}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  {pontosValidos.map((cliente, idx) => {
                    const lat = Number(cliente.latitude)
                    const lng = Number(cliente.longitude)
                    const popupMatch = cliente.cod_id ? matchMap[cliente.cod_id] : undefined
                    return (
                      <Marker
                        key={cliente.cod_id || idx}
                        position={[lat, lng]}
                        icon={cliente.possui_solar ? solarIcon : normalIcon}
                      >
                        <Popup>
                          <div className="min-w-[220px]">
                            <h3 className="font-bold text-base text-teal-800 mb-2">
                              📍 {cliente.nome_municipio || cliente.mun || 'Cliente'}
                            </h3>
                            <div className="space-y-1 text-sm">
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">UF:</span>
                                <span>{cliente.nome_uf || '-'}</span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Classe:</span>
                                <span>
                                  {cliente.clas_sub_descricao || cliente.clas_sub || '-'}
                                </span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Grupo:</span>
                                <span>{cliente.gru_tar || '-'}</span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Cons. Medio:</span>
                                <span className="font-semibold text-green-700">
                                  {cliente.consumo_medio?.toLocaleString('pt-BR') || '-'} kWh
                                </span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Cons. Anual:</span>
                                <span className="font-semibold text-blue-700">
                                  {cliente.consumo_anual?.toLocaleString('pt-BR') || '-'} kWh
                                </span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Carga Inst:</span>
                                <span className="font-semibold text-gray-700">
                                  {cliente.car_inst?.toLocaleString('pt-BR') || '-'} kW
                                </span>
                              </div>
                              <div className="flex justify-between pb-1">
                                <span className="font-medium">Solar:</span>
                                <span
                                  className={
                                    cliente.possui_solar ? 'text-green-600' : 'text-red-500'
                                  }
                                >
                                  {cliente.possui_solar ? '☀️ Sim' : '❌ Nao'}
                                </span>
                              </div>
                            </div>
                            {popupMatch && (
                              <div className="mt-2 pt-2 border-t border-purple-200 space-y-1">
                                <div className="flex items-center justify-between">
                                  <span className="text-xs font-mono text-purple-700">
                                    {formatCnpj(popupMatch.cnpj)}
                                  </span>
                                  <span
                                    className={`text-[10px] font-bold px-1 py-0.5 rounded ${
                                      popupMatch.score_total >= 75
                                        ? 'bg-green-100 text-green-700'
                                        : popupMatch.score_total >= 50
                                          ? 'bg-yellow-100 text-yellow-700'
                                          : 'bg-red-100 text-red-700'
                                    }`}
                                  >
                                    {popupMatch.score_total.toFixed(0)}
                                  </span>
                                </div>
                                <p className="text-xs font-semibold text-gray-800 truncate">
                                  {popupMatch.razao_social}
                                </p>
                                {popupMatch.telefone && (
                                  <a
                                    href={`https://wa.me/55${popupMatch.telefone.replace(/\D/g, '')}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-xs text-green-600 hover:underline block"
                                  >
                                    {formatPhone(popupMatch.telefone)}
                                  </a>
                                )}
                              </div>
                            )}
                            <a
                              href={getStreetViewUrl(lat, lng)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-3 block w-full text-center px-3 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-lg text-sm transition-colors"
                            >
                              🚶 Abrir Street View
                            </a>
                          </div>
                        </Popup>
                      </Marker>
                    )
                  })}
                </MapContainer>
              ) : (
                <div className="h-[250px] md:h-[350px] flex items-center justify-center bg-gray-50 dark:bg-gray-800">
                  <div className="text-center p-4">
                    <MapPinIcon className="w-12 h-12 md:w-16 md:h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                    <p className="text-gray-500 dark:text-gray-400 text-sm md:text-base">
                      Nenhum ponto com coordenadas
                    </p>
                  </div>
                </div>
              )}

              {pontosValidos.length > 0 && (
                <div className="absolute bottom-2 left-2 md:bottom-4 md:left-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-2 md:p-3 text-xs z-[1000]">
                  <div className="font-bold text-gray-800 mb-1 md:mb-2">Legenda:</div>
                  <div className="flex items-center gap-1.5 md:gap-2 mb-1">
                    <span className="w-3 h-3 md:w-4 md:h-4 rounded-full bg-green-500 border-2 border-white shadow"></span>
                    <span className="text-[10px] md:text-xs">Solar</span>
                  </div>
                  <div className="flex items-center gap-1.5 md:gap-2">
                    <span className="w-3 h-3 md:w-4 md:h-4 rounded-full bg-blue-500 border-2 border-white shadow"></span>
                    <span className="text-[10px] md:text-xs">Sem Solar</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Save Query Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-800 dark:text-white mb-4">
              💾 Salvar Consulta B3
            </h3>
            <div className="space-y-4">
              <div>
                <label className="label font-semibold">Nome da Consulta *</label>
                <input
                  type="text"
                  className="input"
                  value={queryName}
                  onChange={(e) => setQueryName(e.target.value)}
                  placeholder="Ex: Clientes B2 com Solar em SP"
                />
              </div>
              <div>
                <label className="label font-semibold">Descricao (opcional)</label>
                <textarea
                  className="input"
                  rows={3}
                  value={queryDescription}
                  onChange={(e) => setQueryDescription(e.target.value)}
                  placeholder="Descreva esta consulta..."
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleSaveQuery}
                  disabled={salvarConsultaMutation.isPending}
                  className="btn-primary flex-1"
                >
                  {salvarConsultaMutation.isPending ? 'Salvando...' : '💾 Salvar'}
                </button>
                <button
                  onClick={() => setShowSaveModal(false)}
                  className="bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 px-4 py-2 rounded-lg font-medium"
                >
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Selection Toolbar */}
      {selectedCodIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 px-5 py-3 bg-teal-700 dark:bg-teal-800 text-white rounded-xl shadow-2xl ring-1 ring-teal-500/30">
          <span className="text-sm font-semibold whitespace-nowrap">
            {selectedCodIds.size} {selectedCodIds.size === 1 ? 'item selecionado' : 'itens selecionados'}
          </span>
          <div className="h-5 w-px bg-teal-500/40" />
          <button
            onClick={handleOpenListasModal}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white/15 hover:bg-white/25 rounded-lg text-sm font-medium transition-colors"
          >
            <ListBulletIcon className="h-4 w-4" />
            Adicionar a Lista
          </button>
          <button
            onClick={() => setSelectedCodIds(new Set())}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-medium transition-colors"
          >
            <XMarkIcon className="h-4 w-4" />
            Limpar selecao
          </button>
        </div>
      )}

      {/* Listas de Prospeccao Modal */}
      {showListasModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full max-h-[85vh] overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b dark:border-gray-700 bg-gradient-to-r from-teal-600 to-cyan-600">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <ListBulletIcon className="h-5 w-5" />
                  Listas de Prospeccao
                </h3>
                <button
                  onClick={() => setShowListasModal(false)}
                  className="text-white/80 hover:text-white text-2xl leading-none"
                >
                  <XMarkIcon className="h-6 w-6" />
                </button>
              </div>
              {selectedCodIds.size > 0 && (
                <p className="text-sm text-teal-100 mt-1">
                  {selectedCodIds.size} UC(s) selecionada(s) para adicionar
                </p>
              )}
            </div>

            <div className="overflow-y-auto max-h-[60vh] p-6 space-y-5">
              {/* Existing lists */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                  Listas existentes
                </h4>
                {listasLoading ? (
                  <div className="flex items-center justify-center py-6">
                    <div className="w-6 h-6 border-2 border-teal-200 border-t-teal-600 rounded-full animate-spin" />
                    <span className="ml-2 text-sm text-gray-500 dark:text-gray-400">Carregando...</span>
                  </div>
                ) : listas.length > 0 ? (
                  <div className="space-y-2">
                    {listas.map((lista) => (
                      <div
                        key={lista.id}
                        className="flex items-center justify-between border dark:border-gray-700 rounded-lg p-3 hover:border-teal-300 dark:hover:border-teal-600 transition-colors bg-gray-50 dark:bg-gray-900/50"
                      >
                        <div className="flex-1 min-w-0">
                          <h5 className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                            {lista.nome}
                          </h5>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-gray-500 dark:text-gray-400">
                              {lista.total_unidades} UC(s)
                            </span>
                            {lista.created_at && (
                              <>
                                <span className="text-xs text-gray-400 dark:text-gray-500">|</span>
                                <span className="text-xs text-gray-400 dark:text-gray-500">
                                  {new Date(lista.created_at).toLocaleDateString('pt-BR')}
                                </span>
                              </>
                            )}
                          </div>
                          {lista.descricao && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">
                              {lista.descricao}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 ml-3 flex-shrink-0">
                          {selectedCodIds.size > 0 && (
                            <button
                              onClick={() => handleAddToLista(lista.id)}
                              disabled={addingToListaId === lista.id}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                            >
                              {addingToListaId === lista.id ? (
                                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                              ) : (
                                <PlusIcon className="h-3.5 w-3.5" />
                              )}
                              Adicionar
                            </button>
                          )}
                          <button
                            onClick={() => handleExportListaCsv(lista.id)}
                            className="inline-flex items-center px-2 py-1.5 bg-green-100 hover:bg-green-200 dark:bg-green-900/30 dark:hover:bg-green-900/50 text-green-700 dark:text-green-400 rounded-lg text-xs font-medium transition-colors"
                            title="Exportar CSV"
                          >
                            <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteLista(lista.id)}
                            className="inline-flex items-center px-2 py-1.5 bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-600 dark:text-red-400 rounded-lg text-xs font-medium transition-colors"
                            title="Excluir lista"
                          >
                            <TrashIcon className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                    Nenhuma lista criada ainda
                  </p>
                )}
              </div>

              {/* Create new list */}
              <div className="border-t dark:border-gray-700 pt-5">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-1.5">
                  <PlusIcon className="h-4 w-4" />
                  Criar Nova Lista
                </h4>
                <div className="space-y-3">
                  <div>
                    <label className="label text-xs font-semibold">Nome da Lista *</label>
                    <input
                      type="text"
                      className="input text-sm"
                      placeholder="Ex: Clientes prioritarios SP"
                      value={novaListaNome}
                      onChange={(e) => setNovaListaNome(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="label text-xs font-semibold">Descricao (opcional)</label>
                    <input
                      type="text"
                      className="input text-sm"
                      placeholder="Breve descricao..."
                      value={novaListaDescricao}
                      onChange={(e) => setNovaListaDescricao(e.target.value)}
                    />
                  </div>
                  <button
                    onClick={handleCreateAndAdd}
                    disabled={creatingLista || !novaListaNome.trim()}
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {creatingLista ? (
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <PlusIcon className="h-4 w-4" />
                    )}
                    {selectedCodIds.size > 0
                      ? `Criar e Adicionar ${selectedCodIds.size} UC(s)`
                      : 'Criar Lista Vazia'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Saved Queries Modal */}
      {showSavedQueries && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b dark:border-gray-700">
              <div className="flex justify-between items-center">
                <h3 className="text-xl font-bold text-gray-800 dark:text-white">
                  📂 Consultas Salvas B3
                </h3>
                <button
                  onClick={() => setShowSavedQueries(false)}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-2xl leading-none"
                >
                  ×
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {consultasSalvas && consultasSalvas.length > 0 ? (
                <div className="space-y-3">
                  {consultasSalvas.map((consulta) => (
                    <div
                      key={consulta.id}
                      className="border dark:border-gray-700 rounded-lg p-4 hover:border-teal-300 dark:hover:border-teal-600 transition-colors"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h4 className="font-bold text-gray-800 dark:text-white">
                            {consulta.name}
                          </h4>
                          {consulta.description && (
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                              {consulta.description}
                            </p>
                          )}
                          <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                            Usado {consulta.use_count}x • Criado em{' '}
                            {new Date(consulta.created_at).toLocaleDateString('pt-BR')}
                          </p>
                        </div>
                        <div className="flex gap-2 ml-4">
                          <button
                            onClick={() => aplicarConsultaSalva(consulta)}
                            className="bg-teal-600 hover:bg-teal-700 text-white px-3 py-1 rounded text-sm font-medium"
                          >
                            Usar
                          </button>
                          <button
                            onClick={() => excluirConsultaMutation.mutate(consulta.id)}
                            className="bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-600 dark:text-red-400 px-3 py-1 rounded text-sm"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  <p className="text-lg">Nenhuma consulta salva</p>
                  <p className="text-sm mt-2">
                    Configure filtros e clique em "💾 Salvar Consulta"
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
