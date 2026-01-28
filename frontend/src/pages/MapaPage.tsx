import { useState, useMemo, useCallback, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Tooltip, useMap, Rectangle, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useQuery, useMutation } from '@tanstack/react-query'
import { aneelApi } from '@/services/api'
import type { MapaAvancadoResponse, PontoMapaCompleto, ConsultaSalva, OpcoesFiltros } from '@/types'
import toast from 'react-hot-toast'
import { MagnifyingGlassIcon, MapPinIcon } from '@heroicons/react/24/outline'

// Ícones customizados para Leaflet
const createCustomIcon = (color: string, size = 12) => L.divIcon({
  className: 'custom-marker',
  html: `<div style="
    width: ${size}px;
    height: ${size}px;
    background-color: ${color};
    border: 2px solid white;
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
  "></div>`,
  iconSize: [size, size],
  iconAnchor: [size/2, size/2],
  popupAnchor: [0, -size/2],
})

const solarLivreIcon = createCustomIcon('#22c55e')
const solarCativoIcon = createCustomIcon('#84cc16')
const normalLivreIcon = createCustomIcon('#3b82f6')
const normalCativoIcon = createCustomIcon('#6366f1')

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

// Componente para seleção de área com cursor de crosshair
function AreaSelector({ 
  isSelecting, 
  onSelect, 
  onCancel 
}: { 
  isSelecting: boolean
  onSelect: (bounds: L.LatLngBounds) => void
  onCancel: () => void
}) {
  const [startPoint, setStartPoint] = useState<L.LatLng | null>(null)
  const [endPoint, setEndPoint] = useState<L.LatLng | null>(null)
  const map = useMap()
  
  // Mudar cursor quando em modo de seleção
  useEffect(() => {
    const container = map.getContainer()
    if (isSelecting) {
      container.style.cursor = 'crosshair'
      // Desabilitar drag do mapa durante seleção
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
        // Só seleciona se a área tiver um tamanho mínimo
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
    }
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
        dashArray: '8, 4'
      }}
    />
  )
}

// Gera URL do Google Maps que busca a visualização Street View mais próxima
// Se não tiver Street View exato, mostra o mapa satélite
const getStreetViewUrl = (lat: number, lng: number) => {
  // Vista de satélite com zoom alto
  return `https://www.google.com/maps/@${lat},${lng},19z/data=!3m1!1e3`
}

// Gera URL que abre Street View buscando automaticamente a cobertura mais próxima
// Usa source=apiv3 que é mais tolerante a pontos fora de ruas
const getStreetViewDirectUrl = (lat: number, lng: number) => {
  // Esta URL força o Google a buscar a panorama Street View mais próxima
  // radius=100 busca num raio de 100m, source=outdoor prioriza vias públicas
  return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}&heading=0&pitch=0&fov=90`
}

export default function MapaPage() {
  // Estados dos filtros
  const [filtros, setFiltros] = useState({
    uf: '',
    municipio: '',
    demanda_min: '',
    demanda_max: '',
    possui_solar: '',
    tipo_consumidor: '',
    classe: '',
    limit: 5000,
  })
  
  // Estados de UI
  const [isSelecting, setIsSelecting] = useState(false)
  const [selectedBounds, setSelectedBounds] = useState<L.LatLngBounds | null>(null)
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [showSavedQueries, setShowSavedQueries] = useState(false)
  const [queryName, setQueryName] = useState('')
  const [queryDescription, setQueryDescription] = useState('')
  const [pontosNaSelecao, setPontosNaSelecao] = useState<PontoMapaCompleto[]>([])
  
  // Carregar opções de filtros (UFs)
  const { data: opcoesFiltros } = useQuery<OpcoesFiltros>({
    queryKey: ['opcoes-filtros'],
    queryFn: aneelApi.opcoesFiltros,
  })
  
  // Carregar dados do mapa
  const { data: mapaData, refetch, isFetching } = useQuery<MapaAvancadoResponse>({
    queryKey: ['mapa-avancado', filtros],
    queryFn: () => aneelApi.mapaAvancado({
      uf: filtros.uf || undefined,
      municipio: filtros.municipio || undefined,
      demanda_min: filtros.demanda_min ? parseFloat(filtros.demanda_min) : undefined,
      demanda_max: filtros.demanda_max ? parseFloat(filtros.demanda_max) : undefined,
      possui_solar: filtros.possui_solar ? filtros.possui_solar === 'true' : undefined,
      tipo_consumidor: filtros.tipo_consumidor || undefined,
      classe: filtros.classe || undefined,
      limit: filtros.limit,
    }),
    enabled: false,
  })
  
  // Carregar consultas salvas
  const { data: consultasSalvas, refetch: refetchSalvas } = useQuery<ConsultaSalva[]>({
    queryKey: ['consultas-salvas', 'mapa'],
    queryFn: () => aneelApi.listarConsultasSalvas('mapa'),
  })
  
  // Mutation para salvar consulta
  const salvarConsultaMutation = useMutation({
    mutationFn: aneelApi.salvarConsulta,
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
    mutationFn: aneelApi.excluirConsultaSalva,
    onSuccess: () => {
      toast.success('Consulta excluída!')
      refetchSalvas()
    },
    onError: () => toast.error('Erro ao excluir'),
  })
  
  // Calcular centro do mapa
  const mapCenter = useMemo<[number, number]>(() => {
    if (!mapaData?.centro) return [-15.7801, -47.9292]
    return [mapaData.centro.lat, mapaData.centro.lng]
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
      const result = await aneelApi.usarConsultaSalva(consulta.id)
      setFiltros({
        uf: result.filters.uf || '',
        municipio: result.filters.municipio || '',
        demanda_min: result.filters.demanda_min?.toString() || '',
        demanda_max: result.filters.demanda_max?.toString() || '',
        possui_solar: result.filters.possui_solar?.toString() || '',
        tipo_consumidor: result.filters.tipo_consumidor || '',
        classe: result.filters.classe || '',
        limit: result.filters.limit || 5000,
      })
      setShowSavedQueries(false)
      toast.success(`Consulta "${consulta.name}" carregada`)
      setTimeout(() => refetch(), 100)
    } catch {
      toast.error('Erro ao carregar consulta')
    }
  }, [refetch])
  
  // Salvar consulta atual
  const handleSaveQuery = useCallback(() => {
    if (!queryName.trim()) {
      toast.error('Digite um nome para a consulta')
      return
    }
    salvarConsultaMutation.mutate({
      name: queryName,
      description: queryDescription,
      filters: filtros,
      query_type: 'mapa',
    })
  }, [queryName, queryDescription, filtros, salvarConsultaMutation])
  
  // Seleção de área
  const handleAreaSelect = useCallback((bounds: L.LatLngBounds) => {
    setSelectedBounds(bounds)
    setIsSelecting(false)
    
    if (mapaData?.pontos) {
      const pontosNaArea = mapaData.pontos.filter(p => 
        p.latitude >= bounds.getSouth() &&
        p.latitude <= bounds.getNorth() &&
        p.longitude >= bounds.getWest() &&
        p.longitude <= bounds.getEast()
      )
      setPontosNaSelecao(pontosNaArea)
      toast.success(`${pontosNaArea.length} pontos selecionados`)
    }
  }, [mapaData])
  
  // Exportar seleção
  const handleExportSelection = useCallback(async (formato: 'xlsx' | 'csv') => {
    if (!selectedBounds) {
      toast.error('Selecione uma área primeiro')
      return
    }
    
    try {
      toast.loading('Preparando exportação...')
      const blob = await aneelApi.exportarSelecaoMapa({
        bounds: {
          north: selectedBounds.getNorth(),
          south: selectedBounds.getSouth(),
          east: selectedBounds.getEast(),
          west: selectedBounds.getWest(),
        },
        filtros: {
          possui_solar: filtros.possui_solar ? filtros.possui_solar === 'true' : undefined,
          tipo_consumidor: filtros.tipo_consumidor || undefined,
        },
        formato,
      })
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `selecao_mapa_${pontosNaSelecao.length}_pontos.${formato}`
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
  }, [selectedBounds, filtros, pontosNaSelecao])
  
  // Limpar seleção
  const clearSelection = useCallback(() => {
    setSelectedBounds(null)
    setPontosNaSelecao([])
    setIsSelecting(false)
  }, [])
  
  // Obter municípios por UF
  const municipiosDisponiveis = useMemo(() => {
    if (!filtros.uf || !opcoesFiltros?.municipios_por_uf) return []
    return opcoesFiltros.municipios_por_uf[filtros.uf] || []
  }, [filtros.uf, opcoesFiltros])
  
  return (
    <div className="min-h-[calc(100vh-8rem)] flex flex-col space-y-4">
      {/* Header */}
      <div className="relative overflow-hidden rounded-xl md:rounded-2xl bg-gradient-to-r from-blue-700 via-blue-600 to-green-500 text-white p-4 md:p-6">
        <div className="relative z-10 flex justify-between items-start">
          <div>
            <h1 className="text-xl md:text-3xl font-bold">🗺️ Mapa Interativo BDGD</h1>
            <p className="text-sm md:text-lg text-white/90 mt-1">
              Visualize, selecione áreas e exporte dados
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowSavedQueries(true)}
              className="bg-white/20 hover:bg-white/30 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              📂 Consultas Salvas
            </button>
          </div>
        </div>
        <div className="absolute -right-8 -top-8 h-24 md:h-32 w-24 md:w-32 rounded-full bg-white/10" />
      </div>
      
      {/* Filtros Expandidos */}
      <div className="card p-3 md:p-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 md:gap-4">
          {/* UF */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">UF</label>
            <select
              className="input text-sm"
              value={filtros.uf}
              onChange={(e) => setFiltros({ ...filtros, uf: e.target.value, municipio: '' })}
            >
              <option value="">Todos</option>
              {opcoesFiltros?.ufs?.map(uf => (
                <option key={uf} value={uf}>{uf}</option>
              ))}
            </select>
          </div>
          
          {/* Município */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Município</label>
            <select
              className="input text-sm"
              value={filtros.municipio}
              onChange={(e) => setFiltros({ ...filtros, municipio: e.target.value })}
              disabled={!filtros.uf}
            >
              <option value="">Todos</option>
              {municipiosDisponiveis.map(mun => (
                <option key={mun} value={mun}>{mun}</option>
              ))}
            </select>
          </div>
          
          {/* Demanda Mín */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Demanda Mín</label>
            <input
              type="number"
              className="input text-sm"
              value={filtros.demanda_min}
              onChange={(e) => setFiltros({ ...filtros, demanda_min: e.target.value })}
              placeholder="0"
            />
          </div>
          
          {/* Demanda Máx */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Demanda Máx</label>
            <input
              type="number"
              className="input text-sm"
              value={filtros.demanda_max}
              onChange={(e) => setFiltros({ ...filtros, demanda_max: e.target.value })}
              placeholder="10000"
            />
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
              <option value="true">☀️ Com Solar</option>
              <option value="false">Sem Solar</option>
            </select>
          </div>
          
          {/* Tipo Consumidor */}
          <div>
            <label className="label text-xs md:text-sm font-semibold">Consumidor</label>
            <select
              className="input text-sm"
              value={filtros.tipo_consumidor}
              onChange={(e) => setFiltros({ ...filtros, tipo_consumidor: e.target.value })}
            >
              <option value="">Todos</option>
              <option value="livre">🔓 Livre</option>
              <option value="cativo">🔒 Cativo</option>
            </select>
          </div>
        </div>
        
        {/* Botões de Ação */}
        <div className="flex flex-wrap gap-2 mt-4">
          <button
            onClick={handleSearch}
            disabled={isFetching}
            className="btn-primary text-sm px-4 py-2"
          >
            {isFetching ? <span className="spinner mr-1" /> : <MagnifyingGlassIcon className="w-4 h-4 mr-1" />}
            🔍 Buscar
          </button>
          
          <button
            onClick={() => setIsSelecting(!isSelecting)}
            className={`text-sm px-4 py-2 rounded-lg font-medium transition-colors ${
              isSelecting 
                ? 'bg-orange-500 text-white' 
                : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
            }`}
          >
            {isSelecting ? '✋ Clique no mapa' : '📐 Selecionar Área'}
          </button>
          
          {selectedBounds && (
            <button
              onClick={clearSelection}
              className="bg-red-100 hover:bg-red-200 text-red-700 text-sm px-4 py-2 rounded-lg font-medium"
            >
              ❌ Limpar Seleção
            </button>
          )}
          
          <button
            onClick={() => setShowSaveModal(true)}
            disabled={!filtros.uf && !filtros.demanda_min && !filtros.demanda_max}
            className="bg-purple-100 hover:bg-purple-200 text-purple-700 text-sm px-4 py-2 rounded-lg font-medium disabled:opacity-50"
          >
            💾 Salvar Consulta
          </button>
        </div>
        
        {/* Estatísticas */}
        {mapaData?.estatisticas && (
          <div className="flex flex-wrap gap-4 mt-4 p-3 bg-gradient-to-r from-blue-50 to-green-50 rounded-lg">
            <div className="text-center">
              <div className="text-lg font-bold text-blue-600">{mapaData.estatisticas.total_pontos}</div>
              <div className="text-xs text-gray-600">📍 Total</div>
              {mapaData.estatisticas.total_pontos >= 5000 && (
                <div className="text-xs text-orange-600 font-medium">⚠️ Limite atingido</div>
              )}
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-yellow-600">{mapaData.estatisticas.com_solar}</div>
              <div className="text-xs text-gray-600">☀️ Solar</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-green-600">{mapaData.estatisticas.livres}</div>
              <div className="text-xs text-gray-600">🔓 Livres</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-gray-600">{mapaData.estatisticas.cativos}</div>
              <div className="text-xs text-gray-600">🔒 Cativos</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-purple-600">
                {mapaData.estatisticas.demanda_media?.toLocaleString('pt-BR', {maximumFractionDigits: 0})} kW
              </div>
              <div className="text-xs text-gray-600">📊 Demanda Média</div>
            </div>
          </div>
        )}
      </div>
      
      {/* Painel de Seleção */}
      {selectedBounds && pontosNaSelecao.length > 0 && (
        <div className="card p-4 bg-gradient-to-r from-orange-50 to-yellow-50 border-2 border-orange-300">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="font-bold text-orange-800">📐 Área Selecionada</h3>
              <p className="text-sm text-orange-600">{pontosNaSelecao.length} pontos na seleção</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleExportSelection('xlsx')}
                className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                📥 Exportar Excel
              </button>
              <button
                onClick={() => handleExportSelection('csv')}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                📥 Exportar CSV
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Mapa com Leaflet */}
      <div className="flex-1 card relative overflow-hidden" style={{ minHeight: 'clamp(400px, 55vh, 700px)' }}>
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
            
            {/* Retângulo da seleção */}
            {selectedBounds && (
              <Rectangle 
                bounds={selectedBounds} 
                pathOptions={{ color: 'orange', weight: 3, fillOpacity: 0.2 }}
              />
            )}
            
            {/* Marcadores */}
            {mapaData.pontos.map((ponto) => {
              const isSolar = ponto.possui_solar
              const isLivre = ponto.tipo_consumidor === 'livre'
              let icon = normalCativoIcon
              if (isSolar && isLivre) icon = solarLivreIcon
              else if (isSolar && !isLivre) icon = solarCativoIcon
              else if (!isSolar && isLivre) icon = normalLivreIcon
              
              return (
                <Marker
                  key={ponto.id}
                  position={[ponto.latitude, ponto.longitude]}
                  icon={icon}
                >
                  <Tooltip 
                    direction="top" 
                    offset={[0, -8]} 
                    opacity={0.95}
                    className="custom-tooltip"
                  >
                    <div className="min-w-[220px] max-w-[280px]">
                      <h3 className="font-bold text-sm text-blue-800 mb-1 flex items-center gap-1">
                        📍 {ponto.titulo || ponto.cod_id}
                        {ponto.possui_solar && <span className="text-yellow-500">☀️</span>}
                      </h3>
                      
                      {/* Badges */}
                      <div className="flex gap-1 mb-2">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                          ponto.tipo_consumidor === 'livre' 
                            ? 'bg-green-100 text-green-700' 
                            : 'bg-gray-100 text-gray-700'
                        }`}>
                          {ponto.tipo_consumidor === 'livre' ? '🔓 LIVRE' : '🔒 CATIVO'}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                          ponto.possui_solar
                            ? 'bg-yellow-100 text-yellow-700' 
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          {ponto.possui_solar ? '☀️ SOLAR' : 'SEM SOLAR'}
                        </span>
                      </div>
                      
                      {/* Dados compactos */}
                      <div className="space-y-1 text-xs border-t pt-1">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Demanda:</span>
                          <span className="font-bold text-green-700">
                            {ponto.demanda?.toLocaleString('pt-BR', {maximumFractionDigits: 0})} kW
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Consumo:</span>
                          <span className="font-bold text-blue-700">
                            {ponto.consumo_medio?.toLocaleString('pt-BR', {maximumFractionDigits: 0})} kWh
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Classe:</span>
                          <span className="font-medium">{ponto.classe || '-'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Município:</span>
                          <span className="font-medium">{ponto.municipio || '-'}</span>
                        </div>
                      </div>
                      
                      {/* Links */}
                      <div className="mt-2 pt-1 border-t flex gap-1 text-xs">
                        <a
                          href={getStreetViewDirectUrl(ponto.latitude, ponto.longitude)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex-1 text-center px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          🚶 Street View
                        </a>
                        <a
                          href={getStreetViewUrl(ponto.latitude, ponto.longitude)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex-1 text-center px-2 py-1 bg-green-600 hover:bg-green-700 text-white font-semibold rounded transition-colors"
                          onClick={(e) => e.stopPropagation()}
                        >
                          🛰️ Satélite
                        </a>
                      </div>
                    </div>
                  </Tooltip>
                </Marker>
              )
            })}
          </MapContainer>
        ) : (
          <div className="h-full flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
            <div className="text-center p-4 md:p-8">
              <MapPinIcon className="w-12 h-12 md:w-20 md:h-20 text-gray-300 mx-auto mb-3 md:mb-4" />
              <h3 className="text-lg md:text-2xl font-bold text-gray-700 mb-2">
                Nenhum ponto carregado
              </h3>
              <p className="text-sm md:text-base text-gray-500 max-w-md">
                Use os filtros e clique em <strong>"Buscar"</strong> para visualizar os clientes
              </p>
            </div>
          </div>
        )}
        
        {/* Legenda expandida */}
        {mapaData?.pontos && mapaData.pontos.length > 0 && (
          <div className="absolute bottom-2 left-2 md:bottom-4 md:left-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 text-xs md:text-sm z-[1000]">
            <div className="font-bold text-gray-800 mb-2">Legenda:</div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-yellow-500 border-2 border-green-500 shadow"></span>
                <span>☀️🔓 Solar + Livre</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-yellow-500 border-2 border-gray-400 shadow"></span>
                <span>☀️🔒 Solar + Cativo</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-green-500 border-2 border-white shadow"></span>
                <span>🔓 Livre</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-blue-500 border-2 border-white shadow"></span>
                <span>🔒 Cativo</span>
              </div>
            </div>
          </div>
        )}
        
        {/* Instruções de seleção - mais visíveis */}
        {isSelecting && (
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000]">
            <div className="bg-orange-600 text-white px-6 py-3 rounded-xl shadow-2xl border-2 border-orange-400">
              <div className="flex items-center gap-3">
                <span className="text-2xl">✛</span>
                <div>
                  <p className="font-bold text-lg">Modo Seleção Ativo</p>
                  <p className="text-sm text-orange-100">Clique e arraste para desenhar um retângulo • ESC para cancelar</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* Modal Salvar Consulta */}
      {showSaveModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-800 mb-4">💾 Salvar Consulta</h3>
            <div className="space-y-4">
              <div>
                <label className="label font-semibold">Nome da Consulta *</label>
                <input
                  type="text"
                  className="input"
                  value={queryName}
                  onChange={(e) => setQueryName(e.target.value)}
                  placeholder="Ex: Clientes A4 com Solar em SP"
                />
              </div>
              <div>
                <label className="label font-semibold">Descrição (opcional)</label>
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
                  className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-4 py-2 rounded-lg font-medium"
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
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b">
              <div className="flex justify-between items-center">
                <h3 className="text-xl font-bold text-gray-800">📂 Consultas Salvas</h3>
                <button
                  onClick={() => setShowSavedQueries(false)}
                  className="text-gray-500 hover:text-gray-700 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {consultasSalvas && consultasSalvas.length > 0 ? (
                <div className="space-y-3">
                  {consultasSalvas.map((consulta) => (
                    <div key={consulta.id} className="border rounded-lg p-4 hover:border-blue-300 transition-colors">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <h4 className="font-bold text-gray-800">{consulta.name}</h4>
                          {consulta.description && (
                            <p className="text-sm text-gray-600 mt-1">{consulta.description}</p>
                          )}
                          <p className="text-xs text-gray-400 mt-2">
                            Usado {consulta.use_count}x • Criado em {new Date(consulta.created_at).toLocaleDateString('pt-BR')}
                          </p>
                        </div>
                        <div className="flex gap-2 ml-4">
                          <button
                            onClick={() => aplicarConsultaSalva(consulta)}
                            className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm font-medium"
                          >
                            ▶️ Usar
                          </button>
                          <button
                            onClick={() => excluirConsultaMutation.mutate(consulta.id)}
                            className="bg-red-100 hover:bg-red-200 text-red-600 px-3 py-1 rounded text-sm"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <p className="text-lg">Nenhuma consulta salva</p>
                  <p className="text-sm mt-2">Configure filtros e clique em "Salvar Consulta"</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
