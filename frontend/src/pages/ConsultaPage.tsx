import { useState, useMemo, memo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { aneelApi } from '@/services/api'
import type { FiltroConsulta, ConsultaResponse, OpcoesFiltros, ClienteANEEL } from '@/types'
import toast from 'react-hot-toast'
import {
  MagnifyingGlassIcon,
  ArrowDownTrayIcon,
  FunnelIcon,
  XMarkIcon,
  MapPinIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useDebounce } from '@/hooks/usePerformance'
import { TableSkeleton, MapSkeleton } from '@/components/Skeleton'

// Ícones customizados para Leaflet
const createCustomIcon = (color: string) => L.divIcon({
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

// Função para gerar link do Google Maps Street View
const getStreetViewUrl = (lat: number, lng: number) => {
  return `https://www.google.com/maps/@${lat},${lng},3a,75y,90t/data=!3m6!1e1!3m4!1s!2e0!7i16384!8i8192?entry=ttu`
}

// Componente memoizado para linha da tabela (evita re-renders)
const TableRow = memo(({ cliente }: { cliente: ClienteANEEL }) => {
  const lat = cliente.point_y || cliente.latitude
  const lng = cliente.point_x || cliente.longitude
  const hasCoords = lat && lng
  
  return (
    <tr className="hover:bg-blue-50 transition-colors">
      <td className="px-2 py-1.5 text-xs font-semibold text-gray-900">
        {cliente.nome_uf || '-'}
      </td>
      <td className="px-2 py-1.5 text-xs text-gray-800">
        {cliente.nome_municipio || cliente.mun || '-'}
      </td>
      <td className="px-2 py-1.5 text-xs text-gray-600">
        {cliente.clas_sub_descricao || cliente.clas_sub || '-'}
      </td>
      <td className="px-2 py-1.5 text-xs text-gray-600 font-medium">
        {cliente.gru_tar || '-'}
      </td>
      <td className="px-2 py-1.5 text-xs text-center">
        <span className={clsx(
          'px-1.5 py-0.5 rounded text-xs font-medium',
          cliente.liv === 1 ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'
        )}>
          {cliente.liv === 1 ? 'Livre' : cliente.liv === 0 ? 'Cativo' : '-'}
        </span>
      </td>
      <td className="px-2 py-1.5 text-xs text-right font-mono font-semibold text-green-700">
        {cliente.dem_cont?.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) || '-'}
      </td>
      <td className="px-2 py-1.5 text-xs text-right font-mono text-gray-600">
        {cliente.car_inst?.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) || '-'}
      </td>
      <td className="px-2 py-1.5 text-xs text-right font-mono font-semibold text-blue-700">
        {cliente.ene_max?.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) || '-'}
      </td>
      <td className="px-2 py-1.5 text-center">
        <span className={clsx(
          'inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold',
          cliente.possui_solar 
            ? 'bg-green-100 text-green-700' 
            : 'bg-red-50 text-red-400'
        )}>
          {cliente.possui_solar ? '☀️' : '—'}
        </span>
      </td>
      <td className="px-2 py-1.5 text-center">
        {hasCoords ? (
          <a
            href={getStreetViewUrl(Number(lat), Number(lng))}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center px-2 py-1 bg-blue-100 hover:bg-blue-200 text-blue-700 font-semibold rounded text-xs transition-colors"
            title={`Ver no Street View: ${Number(lat).toFixed(4)}, ${Number(lng).toFixed(4)}`}
          >
            🚶 Ver
          </a>
        ) : (
          <span className="text-gray-300 text-xs">—</span>
        )}
      </td>
    </tr>
  )
})
TableRow.displayName = 'TableRow'

export default function ConsultaPage() {
  const [showFilters, setShowFilters] = useState(true)
  const [resultados, setResultados] = useState<ConsultaResponse | null>(null)
  const [selectedUf, setSelectedUf] = useState('')
  const [selectedMunicipios, setSelectedMunicipios] = useState<string[]>([])
  const [selectedMicrorregioes, setSelectedMicrorregioes] = useState<string[]>([])
  const [selectedMesorregioes, setSelectedMesorregioes] = useState<string[]>([])
  const [selectedClasses, setSelectedClasses] = useState<string[]>([])
  const [selectedGrupos, setSelectedGrupos] = useState<string[]>([])
  const [solarFilter, setSolarFilter] = useState({ com: false, sem: false })
  const [demandaOperador, setDemandaOperador] = useState<'Todos' | 'Maior que' | 'Menor que'>('Todos')
  const [demandaValor, setDemandaValor] = useState<number>(0)
  const [energiaOperador, setEnergiaOperador] = useState<'Todos' | 'Maior que' | 'Menor que'>('Todos')
  const [energiaValor, setEnergiaValor] = useState<number>(0)

  // Filtros de busca por texto com debounce para melhor performance
  const [searchMunicipio, setSearchMunicipio] = useState('')
  const [searchMicrorregiao, setSearchMicrorregiao] = useState('')
  const [searchMesorregiao, setSearchMesorregiao] = useState('')
  const [searchClasse, setSearchClasse] = useState('')
  const [searchGrupo, setSearchGrupo] = useState('')
  
  // Aplicar debounce nos valores de busca (300ms de delay)
  const debouncedSearchMunicipio = useDebounce(searchMunicipio, 200)
  const debouncedSearchMicrorregiao = useDebounce(searchMicrorregiao, 200)
  const debouncedSearchMesorregiao = useDebounce(searchMesorregiao, 200)
  const debouncedSearchClasse = useDebounce(searchClasse, 200)
  const debouncedSearchGrupo = useDebounce(searchGrupo, 200)

  // Pontos válidos para o mapa - memoizado
  const pontosValidos = useMemo(() => {
    if (!resultados?.dados) return []
    return resultados.dados.filter((cliente) => {
      const lat = cliente.point_y || cliente.latitude
      const lng = cliente.point_x || cliente.longitude
      return lat && lng
    })
  }, [resultados])
  
  const { register, handleSubmit, reset, getValues } = useForm<FiltroConsulta>({
    defaultValues: {
      page: 1,
      per_page: 100,
    },
  })
  
  const { data: opcoesFiltros } = useQuery<OpcoesFiltros>({
    queryKey: ['opcoes-filtros'],
    queryFn: aneelApi.opcoesFiltros,
  })
  
  const buildFiltros = () => {
    const valores = getValues()
    const filtros: FiltroConsulta = {
      ...valores,
      uf: selectedUf || undefined,
      municipios: selectedMunicipios.length ? selectedMunicipios : undefined,
      microrregioes: selectedMicrorregioes.length ? selectedMicrorregioes : undefined,
      mesorregioes: selectedMesorregioes.length ? selectedMesorregioes : undefined,
      classes_cliente: selectedClasses.length ? selectedClasses : undefined,
      grupos_tarifarios: selectedGrupos.length ? selectedGrupos : undefined,
    }

    if (solarFilter.com && !solarFilter.sem) {
      filtros.possui_solar = true
    } else if (!solarFilter.com && solarFilter.sem) {
      filtros.possui_solar = false
    } else {
      filtros.possui_solar = undefined
    }

    if (demandaOperador === 'Maior que' && demandaValor > 0) {
      filtros.demanda_min = demandaValor
      filtros.demanda_max = undefined
    } else if (demandaOperador === 'Menor que' && demandaValor > 0) {
      filtros.demanda_max = demandaValor
      filtros.demanda_min = undefined
    } else {
      filtros.demanda_min = undefined
      filtros.demanda_max = undefined
    }

    if (energiaOperador === 'Maior que' && energiaValor > 0) {
      filtros.energia_max_min = energiaValor
      filtros.energia_max_max = undefined
    } else if (energiaOperador === 'Menor que' && energiaValor > 0) {
      filtros.energia_max_max = energiaValor
      filtros.energia_max_min = undefined
    } else {
      filtros.energia_max_min = undefined
      filtros.energia_max_max = undefined
    }

    return filtros
  }

  const consultaMutation = useMutation({
    mutationFn: (filtros: FiltroConsulta) => aneelApi.consulta(filtros),
    onSuccess: (data) => {
      setResultados(data)
      toast.success(`${data.total} registros encontrados`)
    },
    onError: () => {
      toast.error('Erro ao realizar consulta')
    },
  })
  
  const exportarCsvMutation = useMutation({
    mutationFn: () => aneelApi.exportarCsv(buildFiltros()),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'dados_aneel.csv'
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success('CSV exportado com sucesso')
    },
    onError: () => {
      toast.error('Erro ao exportar CSV')
    },
  })
  
  const exportarXlsxMutation = useMutation({
    mutationFn: () => aneelApi.exportarXlsx(buildFiltros()),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'dados_aneel.xlsx'
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success('XLSX exportado com sucesso')
    },
    onError: () => {
      toast.error('Erro ao exportar XLSX')
    },
  })
  
  const exportarKmlMutation = useMutation({
    mutationFn: () => aneelApi.exportarKml(buildFiltros()),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'dados_aneel.kml'
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success('KML exportado com sucesso')
    },
    onError: () => {
      toast.error('Erro ao exportar KML')
    },
  })
  
  const onSubmit = () => {
    consultaMutation.mutate(buildFiltros())
  }

  const handleReset = () => {
    reset()
    setSelectedUf('')
    setSelectedMunicipios([])
    setSelectedMicrorregioes([])
    setSelectedMesorregioes([])
    setSelectedClasses([])
    setSelectedGrupos([])
    setSolarFilter({ com: false, sem: false })
    setDemandaOperador('Todos')
    setDemandaValor(0)
    setEnergiaOperador('Todos')
    setEnergiaValor(0)
    setSearchMunicipio('')
    setSearchMicrorregiao('')
    setSearchMesorregiao('')
    setSearchClasse('')
    setSearchGrupo('')
  }

  const municipiosOptions = selectedUf && opcoesFiltros?.municipios_por_uf?.[selectedUf]
    ? opcoesFiltros.municipios_por_uf[selectedUf]
    : opcoesFiltros?.municipios || []

  const microrregioesOptions = selectedUf && opcoesFiltros?.microrregioes_por_uf?.[selectedUf]
    ? opcoesFiltros.microrregioes_por_uf[selectedUf]
    : opcoesFiltros?.microrregioes || []

  const mesorregioesOptions = selectedUf && opcoesFiltros?.mesorregioes_por_uf?.[selectedUf]
    ? opcoesFiltros.mesorregioes_por_uf[selectedUf]
    : opcoesFiltros?.mesorregioes || []

  // Filtrar opções com base na busca por texto (usando valores debounced)
  const filteredMunicipios = useMemo(() => {
    if (!debouncedSearchMunicipio.trim()) return municipiosOptions.slice(0, 100)
    const search = debouncedSearchMunicipio.toLowerCase()
    return municipiosOptions.filter((m) => m.toLowerCase().includes(search)).slice(0, 100)
  }, [municipiosOptions, debouncedSearchMunicipio])

  const filteredMicrorregioes = useMemo(() => {
    if (!debouncedSearchMicrorregiao.trim()) return microrregioesOptions.slice(0, 50)
    const search = debouncedSearchMicrorregiao.toLowerCase()
    return microrregioesOptions.filter((m) => m.toLowerCase().includes(search)).slice(0, 50)
  }, [microrregioesOptions, debouncedSearchMicrorregiao])

  const filteredMesorregioes = useMemo(() => {
    if (!debouncedSearchMesorregiao.trim()) return mesorregioesOptions.slice(0, 50)
    const search = debouncedSearchMesorregiao.toLowerCase()
    return mesorregioesOptions.filter((m) => m.toLowerCase().includes(search)).slice(0, 50)
  }, [mesorregioesOptions, debouncedSearchMesorregiao])

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

  // Calcular centro do mapa baseado nos pontos
  const mapCenter = useMemo(() => {
    if (pontosValidos.length === 0) return { lat: -15.7801, lng: -47.9292 }
    const lats = pontosValidos.map(c => Number(c.point_y || c.latitude))
    const lngs = pontosValidos.map(c => Number(c.point_x || c.longitude))
    return {
      lat: lats.reduce((a, b) => a + b, 0) / lats.length,
      lng: lngs.reduce((a, b) => a + b, 0) / lngs.length,
    }
  }, [pontosValidos])
  
  return (
    <div className="space-y-4">
      {/* Header Grande e Destacado */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-primary-700 via-primary-600 to-secondary-500 text-white p-6 md:p-8">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight">⚡ Consulta BDGD</h1>
            <p className="text-lg md:text-xl text-white/90 mt-2 font-medium">
              Base de Dados Geográfica da Distribuidora - ANEEL
            </p>
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="btn-outline bg-white/10 border-white/20 text-white hover:bg-white/20 text-lg px-6 py-3"
          >
            {showFilters ? <XMarkIcon className="w-6 h-6" /> : <FunnelIcon className="w-6 h-6" />}
            <span className="ml-2 font-semibold">{showFilters ? 'Ocultar Filtros' : 'Mostrar Filtros'}</span>
          </button>
        </div>
        <div className="absolute -right-8 -top-8 h-40 w-40 rounded-full bg-white/10" />
        <div className="absolute -left-10 -bottom-10 h-48 w-48 rounded-full bg-white/10" />
      </div>
      
      {/* Filtros */}
      {showFilters && (
        <form onSubmit={handleSubmit(onSubmit)} className="card p-6 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Localização */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                <div className="h-2 w-2 rounded-full bg-primary-500" />
                Localização
              </div>
              <div>
                <label className="label">UF</label>
                <select
                  className="input"
                  value={selectedUf}
                  onChange={(e) => {
                    setSelectedUf(e.target.value)
                    setSelectedMunicipios([])
                    setSelectedMicrorregioes([])
                    setSelectedMesorregioes([])
                  }}
                >
                  <option value="">Todas</option>
                  {opcoesFiltros?.ufs?.map((uf) => (
                    <option key={uf} value={uf}>{uf}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">
                  Municípios
                  {selectedMunicipios.length > 0 && (
                    <span className="ml-2 text-xs text-primary-600">({selectedMunicipios.length} selecionados)</span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="🔍 Buscar município..."
                  className="input mb-1 text-sm"
                  value={searchMunicipio}
                  onChange={(e) => setSearchMunicipio(e.target.value)}
                />
                <div className="border border-gray-300 rounded-lg max-h-32 overflow-y-auto bg-white">
                  {municipiosOptions.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Selecione uma UF primeiro</p>
                  ) : filteredMunicipios.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Nenhum resultado para "{searchMunicipio}"</p>
                  ) : (
                    filteredMunicipios.map((mun) => (
                      <label key={mun} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0">
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                          checked={selectedMunicipios.includes(mun)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedMunicipios([...selectedMunicipios, mun])
                            } else {
                              setSelectedMunicipios(selectedMunicipios.filter((m) => m !== mun))
                            }
                          }}
                        />
                        <span className="text-sm text-gray-700">{mun}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
              <div>
                <label className="label">
                  Microrregião
                  {selectedMicrorregioes.length > 0 && (
                    <span className="ml-2 text-xs text-primary-600">({selectedMicrorregioes.length} selecionados)</span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="🔍 Buscar microrregião..."
                  className="input mb-1 text-sm"
                  value={searchMicrorregiao}
                  onChange={(e) => setSearchMicrorregiao(e.target.value)}
                />
                <div className="border border-gray-300 rounded-lg max-h-32 overflow-y-auto bg-white">
                  {microrregioesOptions.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Selecione uma UF primeiro</p>
                  ) : filteredMicrorregioes.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Nenhum resultado para "{searchMicrorregiao}"</p>
                  ) : (
                    filteredMicrorregioes.map((micro) => (
                      <label key={micro} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0">
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                          checked={selectedMicrorregioes.includes(micro)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedMicrorregioes([...selectedMicrorregioes, micro])
                            } else {
                              setSelectedMicrorregioes(selectedMicrorregioes.filter((m) => m !== micro))
                            }
                          }}
                        />
                        <span className="text-sm text-gray-700">{micro}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
              <div>
                <label className="label">
                  Mesorregião
                  {selectedMesorregioes.length > 0 && (
                    <span className="ml-2 text-xs text-primary-600">({selectedMesorregioes.length} selecionados)</span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="🔍 Buscar mesorregião..."
                  className="input mb-1 text-sm"
                  value={searchMesorregiao}
                  onChange={(e) => setSearchMesorregiao(e.target.value)}
                />
                <div className="border border-gray-300 rounded-lg max-h-32 overflow-y-auto bg-white">
                  {mesorregioesOptions.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Selecione uma UF primeiro</p>
                  ) : filteredMesorregioes.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Nenhum resultado para "{searchMesorregiao}"</p>
                  ) : (
                    filteredMesorregioes.map((meso) => (
                      <label key={meso} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0">
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                          checked={selectedMesorregioes.includes(meso)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedMesorregioes([...selectedMesorregioes, meso])
                            } else {
                              setSelectedMesorregioes(selectedMesorregioes.filter((m) => m !== meso))
                            }
                          }}
                        />
                        <span className="text-sm text-gray-700">{meso}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Perfil do cliente */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                <div className="h-2 w-2 rounded-full bg-secondary-500" />
                Perfil do Cliente
              </div>
              <div>
                <label className="label">
                  Classe do Cliente (CLAS_SUB)
                  {selectedClasses.length > 0 && (
                    <span className="ml-2 text-xs text-primary-600">({selectedClasses.length} selecionados)</span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="🔍 Buscar classe..."
                  className="input mb-1 text-sm"
                  value={searchClasse}
                  onChange={(e) => setSearchClasse(e.target.value)}
                />
                <div className="border border-gray-300 rounded-lg max-h-36 overflow-y-auto bg-white">
                  {filteredClasses.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Nenhum resultado para "{searchClasse}"</p>
                  ) : (
                    filteredClasses.map((classe) => (
                      <label key={classe} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0">
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                          checked={selectedClasses.includes(classe)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedClasses([...selectedClasses, classe])
                            } else {
                              setSelectedClasses(selectedClasses.filter((c) => c !== classe))
                            }
                          }}
                        />
                        <span className="text-sm text-gray-700">{classe}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
              <div>
                <label className="label">
                  Grupo Tarifário (GRU_TAR)
                  {selectedGrupos.length > 0 && (
                    <span className="ml-2 text-xs text-primary-600">({selectedGrupos.length} selecionados)</span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="🔍 Buscar grupo..."
                  className="input mb-1 text-sm"
                  value={searchGrupo}
                  onChange={(e) => setSearchGrupo(e.target.value)}
                />
                <div className="border border-gray-300 rounded-lg max-h-32 overflow-y-auto bg-white">
                  {filteredGrupos.length === 0 ? (
                    <p className="p-2 text-sm text-gray-500 italic">Nenhum resultado para "{searchGrupo}"</p>
                  ) : (
                    filteredGrupos.map((gru) => (
                      <label key={gru} className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0">
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                          checked={selectedGrupos.includes(gru)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedGrupos([...selectedGrupos, gru])
                            } else {
                              setSelectedGrupos(selectedGrupos.filter((g) => g !== gru))
                            }
                          }}
                        />
                        <span className="text-sm text-gray-700">{gru}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
              <div>
                <label className="label">Tipo de Consumidor (LIV)</label>
                <select className="input" {...register('tipo_consumidor')}>
                  <option value="">Todos</option>
                  {opcoesFiltros?.tipos_consumidor?.map((tipo) => (
                    <option key={tipo} value={tipo}>{tipo}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Geração Solar (CEG_GD)</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300"
                      checked={solarFilter.com}
                      onChange={(e) => setSolarFilter((prev) => ({ ...prev, com: e.target.checked }))}
                    />
                    Possui Solar
                  </label>
                  <label className="flex items-center gap-2 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300"
                      checked={solarFilter.sem}
                      onChange={(e) => setSolarFilter((prev) => ({ ...prev, sem: e.target.checked }))}
                    />
                    Não Possui
                  </label>
                </div>
              </div>
            </div>

            {/* Consumo */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                <div className="h-2 w-2 rounded-full bg-primary-500" />
                Consumo e Demanda
              </div>
              <div className="grid grid-cols-1 gap-3">
                <div>
                  <label className="label">Demanda Contratada (kW)</label>
                  <div className="grid grid-cols-2 gap-2">
                    <select
                      className="input"
                      value={demandaOperador}
                      onChange={(e) => setDemandaOperador(e.target.value as 'Todos' | 'Maior que' | 'Menor que')}
                    >
                      <option value="Todos">Todos</option>
                      <option value="Maior que">Maior que</option>
                      <option value="Menor que">Menor que</option>
                    </select>
                    <input
                      type="number"
                      min={0}
                      step="0.01"
                      className="input"
                      value={demandaValor}
                      onChange={(e) => setDemandaValor(Number(e.target.value))}
                      placeholder="0"
                    />
                  </div>
                </div>
                <div>
                  <label className="label">Energia Máxima (kWh)</label>
                  <div className="grid grid-cols-2 gap-2">
                    <select
                      className="input"
                      value={energiaOperador}
                      onChange={(e) => setEnergiaOperador(e.target.value as 'Todos' | 'Maior que' | 'Menor que')}
                    >
                      <option value="Todos">Todos</option>
                      <option value="Maior que">Maior que</option>
                      <option value="Menor que">Menor que</option>
                    </select>
                    <input
                      type="number"
                      min={0}
                      step="0.01"
                      className="input"
                      value={energiaValor}
                      onChange={(e) => setEnergiaValor(Number(e.target.value))}
                      placeholder="0"
                    />
                  </div>
                </div>
                <div>
                  <label className="label">Registros por página</label>
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
          </div>
          
          {/* Botões */}
          <div className="flex flex-wrap items-center gap-3 pt-4 border-t">
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
            
            <button
              type="button"
              onClick={handleReset}
              className="btn-secondary"
            >
              Limpar Filtros
            </button>
          </div>
        </form>
      )}
      
      {/* Loading State */}
      {consultaMutation.isPending && (
        <div className="space-y-4">
          <div className="card p-5 bg-gradient-to-r from-gray-50 to-white">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">Buscando dados...</h2>
                <p className="text-gray-500">Aguarde enquanto processamos sua consulta</p>
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
      
      {/* Resultados */}
      {resultados && !consultaMutation.isPending && (
        <div className="space-y-4">
          {/* Header dos Resultados com Botões de Download */}
          <div className="card p-5 bg-gradient-to-r from-gray-50 to-white">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
              <div>
                <h2 className="text-2xl md:text-3xl font-bold text-gray-900 flex items-center gap-3">
                  📊 Resultados da Consulta
                </h2>
                <p className="text-lg text-gray-600 mt-2">
                  <span className="font-bold text-2xl text-primary-600">{resultados.total.toLocaleString('pt-BR')}</span> registros encontrados
                  <span className="text-gray-400 mx-2">•</span>
                  Página <span className="font-semibold">{resultados.page}</span> de <span className="font-semibold">{resultados.total_pages}</span>
                </p>
              </div>
              
              {/* Botões de Download Destacados */}
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => exportarCsvMutation.mutate()}
                  disabled={exportarCsvMutation.isPending}
                  className="inline-flex items-center px-5 py-3 bg-green-600 hover:bg-green-700 text-white font-bold rounded-lg transition-colors disabled:opacity-50 text-base shadow-lg hover:shadow-xl"
                >
                  {exportarCsvMutation.isPending ? (
                    <span className="spinner mr-2" />
                  ) : (
                    <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
                  )}
                  📥 CSV
                </button>
                <button
                  onClick={() => exportarXlsxMutation.mutate()}
                  disabled={exportarXlsxMutation.isPending}
                  className="inline-flex items-center px-5 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg transition-colors disabled:opacity-50 text-base shadow-lg hover:shadow-xl"
                >
                  {exportarXlsxMutation.isPending ? (
                    <span className="spinner mr-2" />
                  ) : (
                    <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
                  )}
                  📥 XLSX
                </button>
                <button
                  onClick={() => exportarKmlMutation.mutate()}
                  disabled={exportarKmlMutation.isPending}
                  className="inline-flex items-center px-5 py-3 bg-orange-600 hover:bg-orange-700 text-white font-bold rounded-lg transition-colors disabled:opacity-50 text-base shadow-lg hover:shadow-xl"
                >
                  {exportarKmlMutation.isPending ? (
                    <span className="spinner mr-2" />
                  ) : (
                    <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
                  )}
                  📥 KML
                </button>
              </div>
            </div>
          </div>

          {/* Tabela Compacta com Todas as Informações */}
          <div className="card">
            <div className="overflow-x-auto max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-100 border-y border-gray-200 sticky top-0">
                  <tr>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 uppercase">
                      UF
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 uppercase">
                      Município
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 uppercase">
                      Classe
                    </th>
                    <th className="px-2 py-2 text-left text-xs font-bold text-gray-700 uppercase">
                      Grupo
                    </th>
                    <th className="px-2 py-2 text-center text-xs font-bold text-gray-700 uppercase">
                      LIV
                    </th>
                    <th className="px-2 py-2 text-right text-xs font-bold text-gray-700 uppercase">
                      Demanda
                    </th>
                    <th className="px-2 py-2 text-right text-xs font-bold text-gray-700 uppercase">
                      Carga Inst.
                    </th>
                    <th className="px-2 py-2 text-right text-xs font-bold text-gray-700 uppercase">
                      Energia Máx
                    </th>
                    <th className="px-2 py-2 text-center text-xs font-bold text-gray-700 uppercase">
                      Solar
                    </th>
                    <th className="px-2 py-2 text-center text-xs font-bold text-gray-700 uppercase">
                      📍 Street View
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {resultados.dados.map((cliente, idx) => (
                    <TableRow key={cliente.cod_id || idx} cliente={cliente} />
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Paginação */}
            <div className="px-4 py-3 border-t bg-gray-50 flex flex-col sm:flex-row items-center justify-between gap-3">
              <p className="text-sm text-gray-600">
                Mostrando <span className="font-bold">{((resultados.page - 1) * resultados.per_page) + 1}</span> a{' '}
                <span className="font-bold">{Math.min(resultados.page * resultados.per_page, resultados.total)}</span> de{' '}
                <span className="font-bold text-primary-600">{resultados.total.toLocaleString('pt-BR')}</span> resultados
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
                  ← Anterior
                </button>
                <span className="px-3 py-1 bg-primary-100 text-primary-700 font-bold rounded-lg text-sm">
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
                  Próxima →
                </button>
              </div>
            </div>
          </div>

          {/* Mapa Integrado com Leaflet (OpenStreetMap - Gratuito) */}
          <div className="card ring-4 ring-primary-200 ring-offset-2 shadow-2xl">
            <div className="px-6 py-5 border-b bg-gradient-to-r from-primary-600 to-blue-600">
              <h2 className="text-2xl md:text-3xl font-bold text-white flex items-center gap-3">
                <MapPinIcon className="w-8 h-8 text-white" />
                🗺️ Mapa de Localização
              </h2>
              <p className="text-base text-primary-100 mt-1">
                {pontosValidos.length > 0 
                  ? `📍 ${pontosValidos.length} pontos plotados no mapa • Clique nos marcadores para detalhes`
                  : 'Pontos com coordenadas válidas serão exibidos aqui'}
              </p>
            </div>
            
            <div className="relative">
              {pontosValidos.length > 0 ? (
                <MapContainer
                  center={[mapCenter.lat, mapCenter.lng]}
                  zoom={pontosValidos.length === 1 ? 14 : 5}
                  style={{ height: '700px', width: '100%' }}
                  scrollWheelZoom={true}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  {pontosValidos.map((cliente, idx) => {
                    const lat = Number(cliente.point_y || cliente.latitude)
                    const lng = Number(cliente.point_x || cliente.longitude)
                    return (
                      <Marker
                        key={cliente.cod_id || idx}
                        position={[lat, lng]}
                        icon={cliente.possui_solar ? solarIcon : normalIcon}
                      >
                        <Popup>
                          <div className="min-w-[220px]">
                            <h3 className="font-bold text-base text-blue-800 mb-2">
                              📍 {cliente.nome_municipio || cliente.mun || 'Cliente'}
                            </h3>
                            <div className="space-y-1 text-sm">
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">UF:</span>
                                <span>{cliente.nome_uf || '-'}</span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Classe:</span>
                                <span>{cliente.clas_sub_descricao || cliente.clas_sub || '-'}</span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Grupo:</span>
                                <span>{cliente.gru_tar || '-'}</span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Demanda:</span>
                                <span className="font-semibold text-green-700">
                                  {cliente.dem_cont?.toLocaleString('pt-BR') || '-'} kW
                                </span>
                              </div>
                              <div className="flex justify-between border-b pb-1">
                                <span className="font-medium">Energia Máx:</span>
                                <span className="font-semibold text-blue-700">
                                  {cliente.ene_max?.toLocaleString('pt-BR') || '-'} kWh
                                </span>
                              </div>
                              <div className="flex justify-between pb-1">
                                <span className="font-medium">Solar:</span>
                                <span className={cliente.possui_solar ? 'text-green-600' : 'text-red-500'}>
                                  {cliente.possui_solar ? '☀️ Sim' : '❌ Não'}
                                </span>
                              </div>
                            </div>
                            <a
                              href={getStreetViewUrl(lat, lng)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-3 block w-full text-center px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg text-sm transition-colors"
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
                <div className="h-[450px] flex items-center justify-center bg-gray-50">
                  <div className="text-center">
                    <MapPinIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">Nenhum ponto com coordenadas para exibir</p>
                  </div>
                </div>
              )}
              
              {/* Legenda */}
              <div className="absolute bottom-4 left-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 text-xs z-[1000]">
                <div className="font-bold text-gray-800 mb-2">Legenda:</div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-4 h-4 rounded-full bg-green-500 border-2 border-white shadow"></span>
                  <span>Com Geração Solar</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-4 h-4 rounded-full bg-blue-500 border-2 border-white shadow"></span>
                  <span>Sem Geração Solar</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
