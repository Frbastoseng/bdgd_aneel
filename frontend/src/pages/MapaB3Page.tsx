import { useState, useMemo, useCallback, useEffect, memo } from 'react'
import { MapContainer, TileLayer, Marker, Tooltip, useMap, Rectangle, useMapEvents } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useQuery, useMutation } from '@tanstack/react-query'
import { b3Api } from '@/services/api'
import type { MapaB3Response, PontoMapaB3, OpcoesFiltrosB3, MatchSummary, ConsultaSalva } from '@/types'
import toast from 'react-hot-toast'
import { MagnifyingGlassIcon, MapPinIcon } from '@heroicons/react/24/outline'

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

// Icones customizados para Leaflet - criados uma unica vez
const iconCache: Record<string, L.DivIcon> = {}
const createCustomIcon = (color: string, size = 12) => {
  const key = `${color}-${size}`
  if (!iconCache[key]) {
    iconCache[key] = L.divIcon({
      className: 'custom-marker',
      html: `<div style="
        width: ${size}px;
        height: ${size}px;
        background-color: ${color};
        border: 2px solid white;
        border-radius: 50%;
        box-shadow: 0 1px 4px rgba(0,0,0,0.3);
      "></div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    })
  }
  return iconCache[key]
}

// Cores para B3 (BT): Solar = amarelo/verde, Normal = roxo/indigo por fase
const solarIcon = createCustomIcon('#f59e0b')        // amarelo - solar
const trifasicoIcon = createCustomIcon('#8b5cf6')    // roxo - ABC (trifasico)
const bifasicoIcon = createCustomIcon('#3b82f6')     // azul - AB (bifasico)
const monofasicoIcon = createCustomIcon('#22c55e')   // verde - A (monofasico)
const defaultBtIcon = createCustomIcon('#6366f1')    // indigo - padrao BT

// Funcao para criar icone do cluster customizado
const createClusterCustomIcon = (cluster: L.MarkerCluster) => {
  const count = cluster.getChildCount()
  let size = 'small'
  let bgColor = '#8b5cf6'

  if (count > 100) {
    size = 'large'
    bgColor = '#ef4444'
  } else if (count > 50) {
    size = 'medium'
    bgColor = '#f97316'
  }

  const sizes = { small: 30, medium: 40, large: 50 }
  const dimension = sizes[size as keyof typeof sizes]

  return L.divIcon({
    html: `<div style="
      background-color: ${bgColor};
      width: ${dimension}px;
      height: ${dimension}px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
      font-size: ${dimension / 3}px;
      border: 3px solid white;
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    ">${count}</div>`,
    className: 'custom-cluster-icon',
    iconSize: L.point(dimension, dimension, true),
  })
}

// Componente para controlar o mapa
function MapController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap()
  useEffect(() => {
    if (center[0] !== 0 && center[1] !== 0) {
      map.setView(center, zoom)
    }
  }, [center, zoom, map])
  return null
}

// Componente para selecao de area com cursor de crosshair
function AreaSelector({
  isSelecting,
  onSelect,
  onCancel,
}: {
  isSelecting: boolean
  onSelect: (bounds: L.LatLngBounds) => void
  onCancel: () => void
}) {
  const [startPoint, setStartPoint] = useState<L.LatLng | null>(null)
  const [endPoint, setEndPoint] = useState<L.LatLng | null>(null)
  const map = useMap()

  useEffect(() => {
    const container = map.getContainer()
    if (isSelecting) {
      container.style.cursor = 'crosshair'
      map.dragging.disable()
    } else {
      container.style.cursor = ''
      map.dragging.enable()
    }
    return () => {
      container.style.cursor = ''
      map.dragging.enable()
    }
  }, [isSelecting, map])

  useMapEvents({
    mousedown(e) {
      if (isSelecting) {
        setStartPoint(e.latlng)
        setEndPoint(null)
      }
    },
    mousemove(e) {
      if (isSelecting && startPoint) {
        setEndPoint(e.latlng)
      }
    },
    mouseup(e) {
      if (isSelecting && startPoint) {
        setEndPoint(e.latlng)
        const bounds = L.latLngBounds(startPoint, e.latlng)
        const pixelBounds = map.latLngToContainerPoint(startPoint)
        const pixelEnd = map.latLngToContainerPoint(e.latlng)
        const width = Math.abs(pixelBounds.x - pixelEnd.x)
        const height = Math.abs(pixelBounds.y - pixelEnd.y)
        if (width > 20 && height > 20) {
          onSelect(bounds)
        }
        setStartPoint(null)
        setEndPoint(null)
      }
    },
    keydown(e) {
      if (e.originalEvent.key === 'Escape') {
        onCancel()
        setStartPoint(null)
        setEndPoint(null)
      }
    },
  })

  if (!startPoint || !endPoint) return null

  const bounds = L.latLngBounds(startPoint, endPoint)

  return (
    <Rectangle
      bounds={bounds}
      pathOptions={{
        color: '#f97316',
        weight: 3,
        fillColor: '#f97316',
        fillOpacity: 0.15,
        dashArray: '8, 4',
      }}
    />
  )
}

const getStreetViewUrl = (lat: number, lng: number) =>
  `https://www.google.com/maps/search/${lat},${lng}/@${lat},${lng},19z`

const getStreetViewDirectUrl = (lat: number, lng: number) =>
  `https://www.google.com/maps/@${lat},${lng},3a,75y,0h,90t/data=!3m4!1e1!3m2!1s!2e0`

// Funcao para obter icone baseado no tipo do ponto B3
const getMarkerIconB3 = (ponto: PontoMapaB3) => {
  if (ponto.possui_solar) return solarIcon
  const fase = (ponto.fas_con || '').toUpperCase()
  if (fase === 'ABC' || fase === 'ABCN') return trifasicoIcon
  if (fase === 'AB' || fase === 'ABN') return bifasicoIcon
  if (fase === 'A' || fase === 'AN') return monofasicoIcon
  return defaultBtIcon
}

// Componente Marker memoizado para performance
const MemoizedMarkerB3 = memo(
  ({ ponto, matchInfo }: { ponto: PontoMapaB3; matchInfo?: MatchSummary }) => {
    const icon = getMarkerIconB3(ponto)

    return (
      <Marker position={[ponto.latitude, ponto.longitude]} icon={icon}>
        <Tooltip direction="top" offset={[0, -6]} opacity={0.95} className="custom-tooltip">
          <div className="min-w-[210px] max-w-[290px]">
            <h3 className="font-bold text-sm text-violet-800 mb-1 flex items-center gap-1">
              {ponto.titulo || ponto.cod_id}
              {ponto.possui_solar && <span className="text-yellow-500">&#9728;</span>}
            </h3>

            {/* Badges */}
            <div className="flex flex-wrap gap-1 mb-2">
              {ponto.fas_con && (
                <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-violet-100 text-violet-700">
                  {ponto.fas_con}
                </span>
              )}
              {ponto.classe && (
                <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-blue-100 text-blue-700">
                  {ponto.classe}
                </span>
              )}
              <span
                className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                  ponto.possui_solar
                    ? 'bg-yellow-100 text-yellow-700'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {ponto.possui_solar ? 'SOLAR' : 'SEM SOLAR'}
              </span>
            </div>

            {/* Dados compactos */}
            <div className="space-y-0.5 text-xs border-t pt-1">
              {ponto.consumo_medio != null && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Consumo Medio:</span>
                  <span className="font-bold text-blue-700">
                    {ponto.consumo_medio.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} kWh
                  </span>
                </div>
              )}
              {ponto.consumo_anual != null && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Consumo Anual:</span>
                  <span className="font-bold text-indigo-700">
                    {ponto.consumo_anual.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} kWh
                  </span>
                </div>
              )}
              {ponto.carga_instalada != null && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Carga Instalada:</span>
                  <span className="font-bold text-green-700">
                    {ponto.carga_instalada.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} kVA
                  </span>
                </div>
              )}
              {ponto.dic_anual != null && (
                <div className="flex justify-between">
                  <span className="text-gray-600">DIC Anual:</span>
                  <span className="font-medium text-orange-600">
                    {ponto.dic_anual.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} h
                  </span>
                </div>
              )}
              {ponto.fic_anual != null && (
                <div className="flex justify-between">
                  <span className="text-gray-600">FIC Anual:</span>
                  <span className="font-medium text-orange-600">
                    {ponto.fic_anual.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} interrup.
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-gray-600">Municipio:</span>
                <span className="font-medium">
                  {ponto.municipio || '-'}
                  {ponto.uf ? ` / ${ponto.uf}` : ''}
                </span>
              </div>
            </div>

            {/* CNPJ Match Info */}
            {matchInfo && (
              <div className="mt-1 pt-1 border-t border-purple-200 space-y-0.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-purple-700">{formatCnpj(matchInfo.cnpj)}</span>
                  <span
                    className={`text-[10px] font-bold px-1 py-0.5 rounded ${
                      matchInfo.score_total >= 75
                        ? 'bg-green-100 text-green-700'
                        : matchInfo.score_total >= 50
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {matchInfo.score_total.toFixed(0)}
                  </span>
                </div>
                <div className="font-semibold text-gray-800 truncate">{matchInfo.razao_social}</div>
                {matchInfo.telefone && (
                  <a
                    href={`https://wa.me/55${matchInfo.telefone.replace(/\D/g, '')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-green-600 hover:underline block"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {formatPhone(matchInfo.telefone)}
                  </a>
                )}
              </div>
            )}

            {/* Links */}
            <div className="mt-2 pt-1 border-t flex gap-1 text-xs">
              <a
                href={getStreetViewUrl(ponto.latitude, ponto.longitude)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 text-center px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                Maps
              </a>
              <a
                href={getStreetViewDirectUrl(ponto.latitude, ponto.longitude)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 text-center px-2 py-1 bg-orange-500 hover:bg-orange-600 text-white font-semibold rounded transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                Street
              </a>
            </div>
          </div>
        </Tooltip>
      </Marker>
    )
  },
  (prevProps, nextProps) =>
    prevProps.ponto.id === nextProps.ponto.id && prevProps.matchInfo === nextProps.matchInfo
)
MemoizedMarkerB3.displayName = 'MemoizedMarkerB3'

export default function MapaB3Page() {
  // Estados dos filtros
  const [filtros, setFiltros] = useState({
    uf: '',
    municipio: '',
    classe: '',
    fas_con: '',
    possui_solar: '',
    consumo_min: '',
    consumo_max: '',
    limit: 5000,
  })

  // Estados de UI
  const [isSelecting, setIsSelecting] = useState(false)
  const [selectedBounds, setSelectedBounds] = useState<L.LatLngBounds | null>(null)
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [showSavedQueries, setShowSavedQueries] = useState(false)
  const [queryName, setQueryName] = useState('')
  const [queryDescription, setQueryDescription] = useState('')
  const [pontosNaSelecao, setPontosNaSelecao] = useState<PontoMapaB3[]>([])
  const [shouldFetch, setShouldFetch] = useState(false)
  const [matchMap, setMatchMap] = useState<Record<string, MatchSummary>>({})

  // Carregar opcoes de filtros B3
  const { data: opcoesFiltros } = useQuery<OpcoesFiltrosB3>({
    queryKey: ['opcoes-filtros-b3'],
    queryFn: b3Api.opcoesFiltros,
  })

  // Carregar dados do mapa B3
  const { data: mapaData, refetch, isFetching } = useQuery<MapaB3Response>({
    queryKey: ['mapa-b3', filtros],
    queryFn: () =>
      b3Api.mapaPontos({
        uf: filtros.uf || undefined,
        municipio: filtros.municipio || undefined,
        possui_solar: filtros.possui_solar ? filtros.possui_solar === 'true' : undefined,
        classe: filtros.classe || undefined,
        fas_con: filtros.fas_con || undefined,
        consumo_min: filtros.consumo_min ? parseFloat(filtros.consumo_min) : undefined,
        consumo_max: filtros.consumo_max ? parseFloat(filtros.consumo_max) : undefined,
        limit: filtros.limit,
      }),
    enabled: false,
  })

  // Carregar consultas salvas B3
  const { data: consultasSalvas, refetch: refetchSalvas } = useQuery<ConsultaSalva[]>({
    queryKey: ['consultas-salvas-b3'],
    queryFn: b3Api.listarConsultasSalvas,
  })

  // Mutation para salvar consulta
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

  // Mutation para excluir consulta
  const excluirConsultaMutation = useMutation({
    mutationFn: b3Api.excluirConsultaSalva,
    onSuccess: () => {
      toast.success('Consulta excluida!')
      refetchSalvas()
    },
    onError: () => toast.error('Erro ao excluir'),
  })

  // Calcular centro do mapa
  const mapCenter = useMemo<[number, number]>(() => {
    if (!mapaData?.centro) return [-15.7801, -47.9292]
    return [mapaData.centro.lat, mapaData.centro.lng]
  }, [mapaData])

  // Efeito para buscar dados quando shouldFetch e true (apos carregar consulta salva)
  useEffect(() => {
    if (shouldFetch) {
      refetch().then((result) => {
        if (result.data?.pontos) {
          toast.success(`${result.data.pontos.length} pontos carregados`)
        }
      })
      setShouldFetch(false)
    }
  }, [shouldFetch, filtros, refetch])

  // Batch lookup CNPJ quando pontos mudam
  useEffect(() => {
    if (!mapaData?.pontos || mapaData.pontos.length === 0) {
      setMatchMap({})
      return
    }
    const codIds = mapaData.pontos
      .map((p) => p.cod_id)
      .filter((id): id is string => !!id)
    if (codIds.length === 0) return

    b3Api
      .batchLookup(codIds.slice(0, 1000))
      .then(setMatchMap)
      .catch(() => { /* silently ignore - CNPJ info is optional */ })
  }, [mapaData])

  // Buscar dados
  const handleSearch = useCallback(() => {
    refetch().then((result) => {
      if (result.data?.pontos) {
        toast.success(`${result.data.pontos.length} pontos carregados`)
      }
    })
  }, [refetch])

  // Aplicar consulta salva
  const aplicarConsultaSalva = useCallback(async (consulta: ConsultaSalva) => {
    try {
      const result = await b3Api.usarConsultaSalva(consulta.id)
      setFiltros({
        uf: result.filters.uf || '',
        municipio: result.filters.municipio || '',
        classe: result.filters.classe || '',
        fas_con: result.filters.fas_con || '',
        possui_solar: result.filters.possui_solar?.toString() || '',
        consumo_min: result.filters.consumo_min?.toString() || '',
        consumo_max: result.filters.consumo_max?.toString() || '',
        limit: result.filters.limit || 5000,
      })
      setShowSavedQueries(false)
      toast.success(`Consulta "${consulta.name}" carregada`)
      setTimeout(() => setShouldFetch(true), 50)
    } catch {
      toast.error('Erro ao carregar consulta')
    }
  }, [])

  // Salvar consulta atual
  const handleSaveQuery = useCallback(() => {
    if (!queryName.trim()) {
      toast.error('Digite um nome para a consulta')
      return
    }
    salvarConsultaMutation.mutate({
      name: queryName,
      description: queryDescription,
      filters: filtros as unknown as Record<string, unknown>,
    })
  }, [queryName, queryDescription, filtros, salvarConsultaMutation])

  // Selecao de area
  const handleAreaSelect = useCallback(
    (bounds: L.LatLngBounds) => {
      setSelectedBounds(bounds)
      setIsSelecting(false)
      if (mapaData?.pontos) {
        const pontosNaArea = mapaData.pontos.filter(
          (p) =>
            p.latitude >= bounds.getSouth() &&
            p.latitude <= bounds.getNorth() &&
            p.longitude >= bounds.getWest() &&
            p.longitude <= bounds.getEast()
        )
        setPontosNaSelecao(pontosNaArea)
        toast.success(`${pontosNaArea.length} pontos selecionados`)
      }
    },
    [mapaData]
  )

  // Exportar selecao
  const handleExportSelection = useCallback(
    async (formato: 'xlsx' | 'csv') => {
      if (!selectedBounds) {
        toast.error('Selecione uma area primeiro')
        return
      }
      try {
        toast.loading('Preparando exportacao...')
        const blob = await b3Api.exportarSelecaoMapa({
          bounds: {
            north: selectedBounds.getNorth(),
            south: selectedBounds.getSouth(),
            east: selectedBounds.getEast(),
            west: selectedBounds.getWest(),
          },
          filtros: {
            possui_solar: filtros.possui_solar ? filtros.possui_solar === 'true' : undefined,
            classe: filtros.classe || undefined,
            fas_con: filtros.fas_con || undefined,
          },
          formato,
        })

        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `selecao_mapa_b3_${pontosNaSelecao.length}_pontos.${formato}`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)

        toast.dismiss()
        toast.success('Arquivo baixado com sucesso!')
      } catch {
        toast.dismiss()
        toast.error('Erro ao exportar dados')
      }
    },
    [selectedBounds, filtros, pontosNaSelecao]
  )

  // Limpar selecao
  const clearSelection = useCallback(() => {
    setSelectedBounds(null)
    setPontosNaSelecao([])
    setIsSelecting(false)
  }, [])

  // Obter municipios por UF
  const municipiosDisponiveis = useMemo(() => {
    if (!filtros.uf || !opcoesFiltros?.municipios_por_uf) return []
    return opcoesFiltros.municipios_por_uf[filtros.uf] || []
  }, [filtros.uf, opcoesFiltros])

  return (
    <div className="min-h-[calc(100vh-8rem)] flex flex-col space-y-4">
      {/* Header */}
      <div className="relative overflow-hidden rounded-xl md:rounded-2xl bg-gradient-to-r from-violet-700 via-purple-600 to-indigo-500 text-white p-4 md:p-6">
        <div className="relative z-10 flex justify-between items-start">
          <div>
            <h1 className="text-xl md:text-3xl font-bold">Mapa BDGD B3</h1>
            <p className="text-sm md:text-lg text-white/90 mt-1">
              Baixa Tensao (BT) — Visualize, selecione areas e exporte dados
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowSavedQueries(true)}
              className="bg-white/20 hover:bg-white/30 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              Consultas Salvas
            </button>
          </div>
        </div>
        <div className="absolute -right-8 -top-8 h-24 md:h-32 w-24 md:w-32 rounded-full bg-white/10" />
      </div>

      {/* Filtros */}
      <div className="card p-3 md:p-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-8 gap-3 md:gap-4">
          {/* UF */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">UF</label>
            <select
              className="input text-sm"
              value={filtros.uf}
              onChange={(e) => setFiltros({ ...filtros, uf: e.target.value, municipio: '' })}
            >
              <option value="">Todos</option>
              {opcoesFiltros?.ufs?.map((uf) => (
                <option key={uf} value={uf}>
                  {uf}
                </option>
              ))}
            </select>
          </div>

          {/* Municipio */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Municipio</label>
            <select
              className="input text-sm"
              value={filtros.municipio}
              onChange={(e) => setFiltros({ ...filtros, municipio: e.target.value })}
              disabled={!filtros.uf}
            >
              <option value="">Todos</option>
              {municipiosDisponiveis.map((mun) => (
                <option key={mun} value={mun}>
                  {mun}
                </option>
              ))}
            </select>
          </div>

          {/* Classe */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Classe</label>
            <select
              className="input text-sm"
              value={filtros.classe}
              onChange={(e) => setFiltros({ ...filtros, classe: e.target.value })}
            >
              <option value="">Todas</option>
              {opcoesFiltros?.classes_cliente?.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Fase Conexao */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Fase Conexao</label>
            <select
              className="input text-sm"
              value={filtros.fas_con}
              onChange={(e) => setFiltros({ ...filtros, fas_con: e.target.value })}
            >
              <option value="">Todas</option>
              {opcoesFiltros?.fases_conexao?.map((f) => (
                <option key={f.codigo} value={f.codigo}>
                  {f.codigo} — {f.descricao}
                </option>
              ))}
            </select>
          </div>

          {/* Solar */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Solar</label>
            <select
              className="input text-sm"
              value={filtros.possui_solar}
              onChange={(e) => setFiltros({ ...filtros, possui_solar: e.target.value })}
            >
              <option value="">Todos</option>
              <option value="true">Com Solar</option>
              <option value="false">Sem Solar</option>
            </select>
          </div>

          {/* Consumo Min */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Consumo Min (kWh)</label>
            <input
              type="number"
              className="input text-sm"
              value={filtros.consumo_min}
              onChange={(e) => setFiltros({ ...filtros, consumo_min: e.target.value })}
              placeholder="0"
            />
          </div>

          {/* Consumo Max */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Consumo Max (kWh)</label>
            <input
              type="number"
              className="input text-sm"
              value={filtros.consumo_max}
              onChange={(e) => setFiltros({ ...filtros, consumo_max: e.target.value })}
              placeholder="10000"
            />
          </div>

          {/* Limite */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Limite</label>
            <select
              className="input text-sm"
              value={filtros.limit}
              onChange={(e) => setFiltros({ ...filtros, limit: parseInt(e.target.value) })}
            >
              <option value={1000}>1.000</option>
              <option value={2000}>2.000</option>
              <option value={5000}>5.000</option>
              <option value={10000}>10.000</option>
              <option value={20000}>20.000</option>
            </select>
          </div>
        </div>

        {/* Botoes de Acao */}
        <div className="flex flex-wrap gap-2 mt-4">
          <button
            onClick={handleSearch}
            disabled={isFetching}
            className="btn-primary text-sm px-4 py-2"
          >
            {isFetching ? (
              <span className="spinner mr-1" />
            ) : (
              <MagnifyingGlassIcon className="w-4 h-4 mr-1" />
            )}
            Buscar
          </button>

          <button
            onClick={() => setIsSelecting(!isSelecting)}
            className={`text-sm px-4 py-2 rounded-lg font-medium transition-colors ${
              isSelecting
                ? 'bg-orange-500 text-white'
                : 'bg-gray-200 hover:bg-gray-300 text-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-200'
            }`}
          >
            {isSelecting ? 'Clique no mapa para selecionar' : 'Selecionar Area'}
          </button>

          {selectedBounds && (
            <button
              onClick={clearSelection}
              className="bg-red-100 hover:bg-red-200 text-red-700 text-sm px-4 py-2 rounded-lg font-medium dark:bg-red-900/30 dark:hover:bg-red-900/50 dark:text-red-300"
            >
              Limpar Selecao
            </button>
          )}

          <button
            onClick={() => setShowSaveModal(true)}
            disabled={!filtros.uf && !filtros.classe && !filtros.fas_con && !filtros.consumo_min && !filtros.consumo_max}
            className="bg-purple-100 hover:bg-purple-200 text-purple-700 text-sm px-4 py-2 rounded-lg font-medium disabled:opacity-50 dark:bg-purple-900/30 dark:hover:bg-purple-900/50 dark:text-purple-300"
          >
            Salvar Consulta
          </button>
        </div>

        {/* Estatisticas */}
        {mapaData?.estatisticas && (
          <div className="flex flex-wrap gap-4 mt-4 p-3 bg-gradient-to-r from-violet-50 to-indigo-50 dark:from-violet-900/20 dark:to-indigo-900/20 rounded-lg">
            <div className="text-center">
              <div className="text-lg font-bold text-violet-600">
                {mapaData.estatisticas.total_pontos.toLocaleString('pt-BR')}
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">Total</div>
              {mapaData.estatisticas.total_pontos >= filtros.limit && (
                <div className="text-xs text-orange-600 font-medium">Limite atingido</div>
              )}
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-yellow-600">
                {mapaData.estatisticas.com_solar.toLocaleString('pt-BR')}
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">Solar</div>
            </div>
            {mapaData.estatisticas.consumo_medio_total != null && (
              <div className="text-center">
                <div className="text-lg font-bold text-blue-600">
                  {mapaData.estatisticas.consumo_medio_total.toLocaleString('pt-BR', {
                    maximumFractionDigits: 0,
                  })}{' '}
                  kWh
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400">Consumo Medio</div>
              </div>
            )}
            <div className="text-center">
              <div className="text-lg font-bold text-gray-500 dark:text-gray-300">
                {Object.keys(matchMap).length > 0
                  ? `${Object.keys(matchMap).length} CNPJs`
                  : '—'}
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">CNPJ Match</div>
            </div>
          </div>
        )}
      </div>

      {/* Painel de Selecao */}
      {selectedBounds && pontosNaSelecao.length > 0 && (
        <div className="card p-4 bg-gradient-to-r from-orange-50 to-yellow-50 dark:from-orange-900/20 dark:to-yellow-900/20 border-2 border-orange-300 dark:border-orange-700">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="font-bold text-orange-800 dark:text-orange-300">Area Selecionada</h3>
              <p className="text-sm text-orange-600 dark:text-orange-400">
                {pontosNaSelecao.length} pontos na selecao
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleExportSelection('xlsx')}
                className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                Exportar Excel
              </button>
              <button
                onClick={() => handleExportSelection('csv')}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                Exportar CSV
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Mapa com Leaflet */}
      <div
        className="flex-1 card relative overflow-hidden"
        style={{ minHeight: 'clamp(400px, 55vh, 700px)' }}
      >
        {mapaData?.pontos && mapaData.pontos.length > 0 ? (
          <MapContainer
            center={mapCenter}
            zoom={mapaData.zoom || 6}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <MapController center={mapCenter} zoom={mapaData.zoom || 6} />
            <AreaSelector
              isSelecting={isSelecting}
              onSelect={handleAreaSelect}
              onCancel={() => setIsSelecting(false)}
            />

            {/* Retangulo da selecao */}
            {selectedBounds && (
              <Rectangle
                bounds={selectedBounds}
                pathOptions={{ color: 'orange', weight: 3, fillOpacity: 0.2 }}
              />
            )}

            {/* Marcadores com Cluster para performance */}
            <MarkerClusterGroup
              chunkedLoading
              iconCreateFunction={createClusterCustomIcon}
              maxClusterRadius={60}
              spiderfyOnMaxZoom={true}
              showCoverageOnHover={false}
              disableClusteringAtZoom={16}
            >
              {mapaData.pontos.map((ponto) => (
                <MemoizedMarkerB3
                  key={ponto.id}
                  ponto={ponto}
                  matchInfo={ponto.cod_id ? matchMap[ponto.cod_id] : undefined}
                />
              ))}
            </MarkerClusterGroup>
          </MapContainer>
        ) : (
          <div className="h-full flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900">
            <div className="text-center p-4 md:p-8">
              <MapPinIcon className="w-12 h-12 md:w-20 md:h-20 text-gray-300 dark:text-gray-600 mx-auto mb-3 md:mb-4" />
              <h3 className="text-lg md:text-2xl font-bold text-gray-700 dark:text-gray-300 mb-2">
                Nenhum ponto carregado
              </h3>
              <p className="text-sm md:text-base text-gray-500 dark:text-gray-400 max-w-md">
                Use os filtros e clique em <strong>"Buscar"</strong> para visualizar os clientes BT
              </p>
            </div>
          </div>
        )}

        {/* Legenda */}
        {mapaData?.pontos && mapaData.pontos.length > 0 && (
          <div className="absolute bottom-2 left-2 md:bottom-4 md:left-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 text-xs md:text-sm z-[1000]">
            <div className="font-bold text-gray-800 mb-2">Legenda:</div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-4 rounded-full border-2 border-white shadow"
                  style={{ backgroundColor: '#f59e0b' }}
                />
                <span>Solar (GD)</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-4 rounded-full border-2 border-white shadow"
                  style={{ backgroundColor: '#8b5cf6' }}
                />
                <span>Trifasico (ABC)</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-4 rounded-full border-2 border-white shadow"
                  style={{ backgroundColor: '#3b82f6' }}
                />
                <span>Bifasico (AB)</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-4 rounded-full border-2 border-white shadow"
                  style={{ backgroundColor: '#22c55e' }}
                />
                <span>Monofasico (A)</span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className="w-4 h-4 rounded-full border-2 border-white shadow"
                  style={{ backgroundColor: '#6366f1' }}
                />
                <span>BT Padrao</span>
              </div>
            </div>
          </div>
        )}

        {/* Instrucoes de selecao */}
        {isSelecting && (
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000]">
            <div className="bg-orange-600 text-white px-6 py-3 rounded-xl shadow-2xl border-2 border-orange-400">
              <div className="flex items-center gap-3">
                <span className="text-2xl font-bold">+</span>
                <div>
                  <p className="font-bold text-lg">Modo Selecao Ativo</p>
                  <p className="text-sm text-orange-100">
                    Clique e arraste para desenhar um retangulo — ESC para cancelar
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modal Salvar Consulta */}
      {showSaveModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">
              Salvar Consulta B3
            </h3>
            <div className="space-y-4">
              <div>
                <label className="label font-semibold">Nome da Consulta *</label>
                <input
                  type="text"
                  className="input"
                  value={queryName}
                  onChange={(e) => setQueryName(e.target.value)}
                  placeholder="Ex: BT Solar em SP — Monofasico"
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
                  {salvarConsultaMutation.isPending ? 'Salvando...' : 'Salvar'}
                </button>
                <button
                  onClick={() => setShowSaveModal(false)}
                  className="bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 px-4 py-2 rounded-lg font-medium"
                >
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Consultas Salvas */}
      {showSavedQueries && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b dark:border-gray-700">
              <div className="flex justify-between items-center">
                <h3 className="text-xl font-bold text-gray-800 dark:text-gray-100">
                  Consultas Salvas B3
                </h3>
                <button
                  onClick={() => setShowSavedQueries(false)}
                  className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 text-2xl"
                >
                  &times;
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {consultasSalvas && consultasSalvas.length > 0 ? (
                <div className="space-y-3">
                  {consultasSalvas.map((consulta) => (
                    <div
                      key={consulta.id}
                      className="border dark:border-gray-700 rounded-lg p-4 hover:border-purple-300 dark:hover:border-purple-600 transition-colors"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h4 className="font-bold text-gray-800 dark:text-gray-100">
                            {consulta.name}
                          </h4>
                          {consulta.description && (
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                              {consulta.description}
                            </p>
                          )}
                          <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                            Usado {consulta.use_count}x &mdash; Criado em{' '}
                            {new Date(consulta.created_at).toLocaleDateString('pt-BR')}
                          </p>
                        </div>
                        <div className="flex gap-2 ml-4">
                          <button
                            onClick={() => aplicarConsultaSalva(consulta)}
                            className="bg-purple-600 hover:bg-purple-700 text-white px-3 py-1 rounded text-sm font-medium"
                          >
                            Usar
                          </button>
                          <button
                            onClick={() => excluirConsultaMutation.mutate(consulta.id)}
                            className="bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-600 dark:text-red-400 px-3 py-1 rounded text-sm"
                          >
                            Excluir
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
                    Configure filtros e clique em "Salvar Consulta"
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
