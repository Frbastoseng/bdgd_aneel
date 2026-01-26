import { useState, useEffect, useRef, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Loader } from '@googlemaps/js-api-loader'
import { aneelApi } from '@/services/api'
import type { FiltroConsulta, ConsultaResponse, OpcoesFiltros } from '@/types'
import toast from 'react-hot-toast'
import {
  MagnifyingGlassIcon,
  ArrowDownTrayIcon,
  FunnelIcon,
  XMarkIcon,
  MapPinIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || ''

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

  // Filtros de busca por texto
  const [searchMunicipio, setSearchMunicipio] = useState('')
  const [searchMicrorregiao, setSearchMicrorregiao] = useState('')
  const [searchMesorregiao, setSearchMesorregiao] = useState('')
  const [searchClasse, setSearchClasse] = useState('')
  const [searchGrupo, setSearchGrupo] = useState('')

  // Mapa
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const streetViewContainerRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<google.maps.Map | null>(null)
  const [streetView, setStreetView] = useState<google.maps.StreetViewPanorama | null>(null)
  const [markers, setMarkers] = useState<google.maps.Marker[]>([])
  const [mapLoaded, setMapLoaded] = useState(false)
  const [showStreetView, setShowStreetView] = useState(false)
  
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

  // Filtrar opções com base na busca por texto
  const filteredMunicipios = useMemo(() => {
    if (!searchMunicipio.trim()) return municipiosOptions
    const search = searchMunicipio.toLowerCase()
    return municipiosOptions.filter((m) => m.toLowerCase().includes(search))
  }, [municipiosOptions, searchMunicipio])

  const filteredMicrorregioes = useMemo(() => {
    if (!searchMicrorregiao.trim()) return microrregioesOptions
    const search = searchMicrorregiao.toLowerCase()
    return microrregioesOptions.filter((m) => m.toLowerCase().includes(search))
  }, [microrregioesOptions, searchMicrorregiao])

  const filteredMesorregioes = useMemo(() => {
    if (!searchMesorregiao.trim()) return mesorregioesOptions
    const search = searchMesorregiao.toLowerCase()
    return mesorregioesOptions.filter((m) => m.toLowerCase().includes(search))
  }, [mesorregioesOptions, searchMesorregiao])

  const filteredClasses = useMemo(() => {
    const classes = opcoesFiltros?.classes_cliente || []
    if (!searchClasse.trim()) return classes
    const search = searchClasse.toLowerCase()
    return classes.filter((c) => c.toLowerCase().includes(search))
  }, [opcoesFiltros?.classes_cliente, searchClasse])

  const filteredGrupos = useMemo(() => {
    const grupos = opcoesFiltros?.grupos_tarifarios || []
    if (!searchGrupo.trim()) return grupos
    const search = searchGrupo.toLowerCase()
    return grupos.filter((g) => g.toLowerCase().includes(search))
  }, [opcoesFiltros?.grupos_tarifarios, searchGrupo])

  // Inicializar Google Maps quando houver resultados
  useEffect(() => {
    if (!resultados || !mapContainerRef.current || mapLoaded) return
    if (!GOOGLE_MAPS_API_KEY) return

    const loader = new Loader({
      apiKey: GOOGLE_MAPS_API_KEY,
      version: 'weekly',
      libraries: ['places'],
    })

    loader.load().then(() => {
      if (!mapContainerRef.current) return

      const mapInstance = new google.maps.Map(mapContainerRef.current, {
        center: { lat: -15.7801, lng: -47.9292 },
        zoom: 4,
        mapTypeControl: true,
        streetViewControl: true,
        fullscreenControl: true,
      })

      setMap(mapInstance)
      setMapLoaded(true)

      if (streetViewContainerRef.current) {
        const streetViewInstance = new google.maps.StreetViewPanorama(streetViewContainerRef.current, {
          position: { lat: -15.7801, lng: -47.9292 },
          pov: { heading: 0, pitch: 0 },
          visible: false,
        })
        mapInstance.setStreetView(streetViewInstance)
        setStreetView(streetViewInstance)
      }
    }).catch((err) => {
      console.error('Erro ao carregar Google Maps:', err)
    })
  }, [resultados, mapLoaded])

  // Atualizar marcadores quando resultados mudarem
  useEffect(() => {
    if (!map || !resultados?.dados) return

    // Limpar marcadores anteriores
    markers.forEach((marker) => marker.setMap(null))

    const newMarkers: google.maps.Marker[] = []
    const bounds = new google.maps.LatLngBounds()
    let pontosValidos = 0

    resultados.dados.forEach((cliente) => {
      const lat = cliente.point_y || cliente.latitude
      const lng = cliente.point_x || cliente.longitude
      
      if (!lat || !lng) return
      
      pontosValidos++
      const position = { lat: Number(lat), lng: Number(lng) }

      const marker = new google.maps.Marker({
        position,
        map,
        title: `Demanda: ${cliente.dem_cont || 'N/A'} kW`,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: cliente.possui_solar ? '#22c55e' : '#3b82f6',
          fillOpacity: 0.8,
          strokeColor: '#ffffff',
          strokeWeight: 2,
        },
      })

      const infoContent = `
        <div style="padding: 8px; min-width: 200px;">
          <h3 style="margin: 0 0 8px 0; font-weight: 600;">
            ${cliente.nome_municipio || cliente.mun || 'Cliente'}
          </h3>
          <div style="font-size: 12px; color: #666;">
            <div><strong>UF:</strong> ${cliente.nome_uf || '-'}</div>
            <div><strong>Classe:</strong> ${cliente.clas_sub_descricao || cliente.clas_sub || '-'}</div>
            <div><strong>Grupo Tarifário:</strong> ${cliente.gru_tar || '-'}</div>
            <div><strong>Demanda:</strong> ${cliente.dem_cont?.toLocaleString('pt-BR') || '-'} kW</div>
            <div><strong>Energia Máx:</strong> ${cliente.ene_max?.toLocaleString('pt-BR') || '-'} kWh</div>
            <div><strong>Solar:</strong> ${cliente.possui_solar ? '✅ Sim' : '❌ Não'}</div>
          </div>
          <div style="margin-top: 8px; font-size: 11px; color: #888;">
            📍 ${Number(lat).toFixed(6)}, ${Number(lng).toFixed(6)}
          </div>
        </div>
      `

      const infoWindow = new google.maps.InfoWindow({ content: infoContent })
      marker.addListener('click', () => infoWindow.open(map, marker))

      newMarkers.push(marker)
      bounds.extend(position)
    })

    setMarkers(newMarkers)

    if (newMarkers.length > 0) {
      map.fitBounds(bounds)
      const listener = google.maps.event.addListener(map, 'idle', () => {
        if (map.getZoom()! > 15) map.setZoom(15)
        google.maps.event.removeListener(listener)
      })
    }
  }, [map, resultados])
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-primary-700 via-primary-600 to-secondary-500 text-white p-6 md:p-8">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-semibold">Consulta BDGD</h1>
            <p className="text-white/90">
              Filtros completos por localidade, classe e consumo
            </p>
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="btn-outline bg-white/10 border-white/20 text-white hover:bg-white/20"
          >
            {showFilters ? <XMarkIcon className="w-5 h-5" /> : <FunnelIcon className="w-5 h-5" />}
            <span className="ml-2">{showFilters ? 'Ocultar Filtros' : 'Mostrar Filtros'}</span>
          </button>
        </div>
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-white/10" />
        <div className="absolute -left-10 -bottom-10 h-40 w-40 rounded-full bg-white/10" />
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
      
      {/* Resultados */}
      {resultados && (
        <div className="space-y-6">
          {/* Header dos Resultados com Botões de Download */}
          <div className="card p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                  📋 Dados Encontrados
                </h2>
                <p className="text-gray-600 mt-1">
                  <span className="font-semibold text-primary-600">{resultados.total.toLocaleString('pt-BR')}</span> registros
                  {' '} • Página {resultados.page} de {resultados.total_pages}
                </p>
              </div>
              
              {/* Botões de Download Destacados */}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => exportarCsvMutation.mutate()}
                  disabled={exportarCsvMutation.isPending}
                  className="inline-flex items-center px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
                >
                  {exportarCsvMutation.isPending ? (
                    <span className="spinner mr-2" />
                  ) : (
                    <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
                  )}
                  📥 Baixar CSV
                </button>
                <button
                  onClick={() => exportarXlsxMutation.mutate()}
                  disabled={exportarXlsxMutation.isPending}
                  className="inline-flex items-center px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
                >
                  {exportarXlsxMutation.isPending ? (
                    <span className="spinner mr-2" />
                  ) : (
                    <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
                  )}
                  📥 Baixar XLSX
                </button>
                <button
                  onClick={() => exportarKmlMutation.mutate()}
                  disabled={exportarKmlMutation.isPending}
                  className="inline-flex items-center px-4 py-2.5 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
                >
                  {exportarKmlMutation.isPending ? (
                    <span className="spinner mr-2" />
                  ) : (
                    <ArrowDownTrayIcon className="w-5 h-5 mr-2" />
                  )}
                  📥 Baixar KML
                </button>
              </div>
            </div>
          </div>

          {/* Tabela de Resultados */}
          <div className="card">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-y border-gray-200">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Município
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Classe
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Grupo Tarifário
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Demanda (kW)
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Energia Máx (kWh)
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Solar
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Coordenadas
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {resultados.dados.map((cliente, idx) => (
                    <tr key={cliente.cod_id || idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {cliente.nome_municipio || cliente.mun}
                        {cliente.nome_uf && (
                          <span className="text-gray-500 ml-1">({cliente.nome_uf})</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {cliente.clas_sub_descricao || cliente.clas_sub}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {cliente.gru_tar}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 text-right font-mono">
                        {cliente.dem_cont?.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 text-right font-mono">
                        {cliente.ene_max?.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={clsx(
                          'badge',
                          cliente.possui_solar ? 'badge-success' : 'badge-gray'
                        )}>
                          {cliente.possui_solar ? 'Sim' : 'Não'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-center">
                        {(cliente.point_y && cliente.point_x) || (cliente.latitude && cliente.longitude) ? (
                          <span className="text-gray-600 font-mono text-xs">
                            {(cliente.point_y || cliente.latitude)?.toFixed(4)}, {(cliente.point_x || cliente.longitude)?.toFixed(4)}
                          </span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Paginação */}
            <div className="card-body border-t flex items-center justify-between">
              <p className="text-sm text-gray-600">
                Mostrando {((resultados.page - 1) * resultados.per_page) + 1} a{' '}
                {Math.min(resultados.page * resultados.per_page, resultados.total)} de{' '}
                {resultados.total.toLocaleString('pt-BR')} resultados
              </p>
              
              <div className="flex items-center gap-2">
                <button
                  disabled={resultados.page <= 1}
                  onClick={() => {
                    const formData = buildFiltros()
                    consultaMutation.mutate({ ...formData, page: resultados.page - 1 })
                  }}
                  className="btn-outline text-sm"
                >
                  Anterior
                </button>
                <button
                  disabled={resultados.page >= resultados.total_pages}
                  onClick={() => {
                    const formData = buildFiltros()
                    consultaMutation.mutate({ ...formData, page: resultados.page + 1 })
                  }}
                  className="btn-outline text-sm"
                >
                  Próxima
                </button>
              </div>
            </div>
          </div>

          {/* Mapa com Coordenadas dos Clientes */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <MapPinIcon className="w-5 h-5 text-primary-600" />
                🗺️ Mapa com Coordenadas dos Clientes
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Pontos com coordenadas válidas desta página
              </p>
            </div>
            
            {GOOGLE_MAPS_API_KEY ? (
              <div className="relative">
                {/* Mapa Principal */}
                <div 
                  ref={mapContainerRef} 
                  className="w-full h-[500px] bg-gray-100"
                />
                
                {/* Street View (overlay) */}
                {showStreetView && (
                  <div className="absolute inset-0 z-10">
                    <div 
                      ref={streetViewContainerRef}
                      className="w-full h-full"
                    />
                    <button
                      onClick={() => {
                        setShowStreetView(false)
                        if (streetView) streetView.setVisible(false)
                      }}
                      className="absolute top-4 right-4 bg-white p-2 rounded-lg shadow-lg hover:bg-gray-100"
                    >
                      <XMarkIcon className="w-6 h-6" />
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 text-center bg-gray-50">
                <MapPinIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600">
                  Configure a API Key do Google Maps no arquivo .env para visualizar o mapa
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  VITE_GOOGLE_MAPS_API_KEY=sua_chave_aqui
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
