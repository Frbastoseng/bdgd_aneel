import { useEffect, useRef, useState, useCallback } from 'react'
import { Loader } from '@googlemaps/js-api-loader'
import { useQuery } from '@tanstack/react-query'
import { aneelApi } from '@/services/api'
import type { PontoMapa, MapaResponse } from '@/types'
import toast from 'react-hot-toast'
import {
  MapPinIcon,
  EyeIcon,
  XMarkIcon,
  ArrowsPointingOutIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'

// API Key do Google Maps (deve ser configurada no .env)
const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || ''

export default function MapaPage() {
  const mapRef = useRef<HTMLDivElement>(null)
  const streetViewRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<google.maps.Map | null>(null)
  const [streetView, setStreetView] = useState<google.maps.StreetViewPanorama | null>(null)
  const [markers, setMarkers] = useState<google.maps.Marker[]>([])
  const [selectedPoint, setSelectedPoint] = useState<PontoMapa | null>(null)
  const [showStreetView, setShowStreetView] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [mapError, setMapError] = useState<string | null>(null)
  
  // Filtros
  const [filtros, setFiltros] = useState({
    demanda_min: '',
    demanda_max: '',
    possui_solar: '',
  })
  
  // Carregar dados do mapa
  const { data: mapaData, refetch } = useQuery<MapaResponse>({
    queryKey: ['mapa-dados', filtros],
    queryFn: () => aneelApi.mapa({
      demanda_min: filtros.demanda_min ? parseFloat(filtros.demanda_min) : undefined,
      demanda_max: filtros.demanda_max ? parseFloat(filtros.demanda_max) : undefined,
      possui_solar: filtros.possui_solar ? filtros.possui_solar === 'true' : undefined,
      limit: 2000,
    }),
    enabled: false,
  })
  
  // Inicializar Google Maps
  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY) {
      setMapError('Configure a API Key do Google Maps no arquivo .env')
      setIsLoading(false)
      return
    }
    
    const loader = new Loader({
      apiKey: GOOGLE_MAPS_API_KEY,
      version: 'weekly',
      libraries: ['places'],
    })
    
    loader.load().then(() => {
      if (!mapRef.current) return
      
      const mapInstance = new google.maps.Map(mapRef.current, {
        center: { lat: -15.7801, lng: -47.9292 }, // Brasília
        zoom: 4,
        mapTypeControl: true,
        streetViewControl: true,
        fullscreenControl: true,
        styles: [
          {
            featureType: 'poi',
            elementType: 'labels',
            stylers: [{ visibility: 'off' }],
          },
        ],
      })
      
      setMap(mapInstance)
      setIsLoading(false)
      
      // Inicializar Street View
      if (streetViewRef.current) {
        const streetViewInstance = new google.maps.StreetViewPanorama(streetViewRef.current, {
          position: { lat: -15.7801, lng: -47.9292 },
          pov: { heading: 0, pitch: 0 },
          visible: false,
        })
        
        mapInstance.setStreetView(streetViewInstance)
        setStreetView(streetViewInstance)
      }
    }).catch((err) => {
      console.error('Erro ao carregar Google Maps:', err)
      setMapError('Erro ao carregar o mapa. Verifique a API Key.')
      setIsLoading(false)
    })
  }, [])
  
  // Atualizar marcadores quando os dados mudarem
  useEffect(() => {
    if (!map || !mapaData?.pontos) return
    
    // Limpar marcadores anteriores
    markers.forEach((marker) => marker.setMap(null))
    
    const newMarkers: google.maps.Marker[] = []
    const bounds = new google.maps.LatLngBounds()
    
    mapaData.pontos.forEach((ponto) => {
      const position = { lat: ponto.latitude, lng: ponto.longitude }
      
      const marker = new google.maps.Marker({
        position,
        map,
        title: ponto.titulo,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: ponto.dados?.possui_solar ? '#22c55e' : '#3b82f6',
          fillOpacity: 0.8,
          strokeColor: '#ffffff',
          strokeWeight: 2,
        },
      })
      
      // Info Window
      const infoWindow = new google.maps.InfoWindow({
        content: `
          <div style="padding: 8px; min-width: 200px;">
            <h3 style="margin: 0 0 8px 0; font-weight: 600;">${ponto.titulo}</h3>
            <p style="margin: 0 0 4px 0; color: #666;">${ponto.descricao || ''}</p>
            ${ponto.dados ? `
              <div style="margin-top: 8px; font-size: 12px;">
                <div><strong>Grupo Tarifário:</strong> ${ponto.dados.gru_tar || '-'}</div>
                <div><strong>Demanda:</strong> ${typeof ponto.dados.dem_cont === 'number' ? ponto.dados.dem_cont.toLocaleString('pt-BR') : '-'} kW</div>
                <div><strong>Energia Máx:</strong> ${typeof ponto.dados.ene_max === 'number' ? ponto.dados.ene_max.toLocaleString('pt-BR') : '-'} kWh</div>
                <div><strong>Solar:</strong> ${ponto.dados.possui_solar ? '✅ Sim' : '❌ Não'}</div>
              </div>
            ` : ''}
            <button onclick="window.openStreetViewForPoint('${ponto.id}')" 
                    style="margin-top: 12px; padding: 6px 12px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer;">
              🚶 Ver Street View
            </button>
          </div>
        `,
      })
      
      marker.addListener('click', () => {
        infoWindow.open(map, marker)
        setSelectedPoint(ponto)
      })
      
      newMarkers.push(marker)
      bounds.extend(position)
    })
    
    setMarkers(newMarkers)
    
    // Ajustar zoom para mostrar todos os pontos
    if (newMarkers.length > 0) {
      map.fitBounds(bounds)
      
      // Limitar zoom máximo
      const listener = google.maps.event.addListener(map, 'idle', () => {
        if (map.getZoom()! > 15) map.setZoom(15)
        google.maps.event.removeListener(listener)
      })
    }
    
    toast.success(`${mapaData.pontos.length} pontos carregados no mapa`)
  }, [map, mapaData])
  
  // Função global para abrir Street View (chamada pelo InfoWindow)
  useEffect(() => {
    (window as unknown as { openStreetViewForPoint: (id: string) => void }).openStreetViewForPoint = (id: string) => {
      const ponto = mapaData?.pontos.find((p) => p.id === id)
      if (ponto && streetView) {
        streetView.setPosition({ lat: ponto.latitude, lng: ponto.longitude })
        streetView.setVisible(true)
        setShowStreetView(true)
        setSelectedPoint(ponto)
      }
    }
    
    return () => {
      delete (window as unknown as { openStreetViewForPoint?: unknown }).openStreetViewForPoint
    }
  }, [mapaData, streetView])
  
  // Abrir Street View para um ponto
  const openStreetView = useCallback((ponto: PontoMapa) => {
    if (streetView) {
      streetView.setPosition({ lat: ponto.latitude, lng: ponto.longitude })
      streetView.setVisible(true)
      setShowStreetView(true)
      setSelectedPoint(ponto)
    }
  }, [streetView])
  
  // Fechar Street View
  const closeStreetView = useCallback(() => {
    if (streetView) {
      streetView.setVisible(false)
      setShowStreetView(false)
    }
  }, [streetView])
  
  // Buscar dados
  const handleSearch = () => {
    refetch()
  }
  
  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Mapa de Clientes</h1>
          <p className="text-gray-600">
            Visualize a localização dos clientes com Street View integrado
          </p>
        </div>
      </div>
      
      {/* Filtros */}
      <div className="card p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="label">Demanda Mínima (kW)</label>
            <input
              type="number"
              className="input w-40"
              value={filtros.demanda_min}
              onChange={(e) => setFiltros({ ...filtros, demanda_min: e.target.value })}
              placeholder="0"
            />
          </div>
          
          <div>
            <label className="label">Demanda Máxima (kW)</label>
            <input
              type="number"
              className="input w-40"
              value={filtros.demanda_max}
              onChange={(e) => setFiltros({ ...filtros, demanda_max: e.target.value })}
              placeholder="10000"
            />
          </div>
          
          <div>
            <label className="label">Geração Solar</label>
            <select
              className="input w-40"
              value={filtros.possui_solar}
              onChange={(e) => setFiltros({ ...filtros, possui_solar: e.target.value })}
            >
              <option value="">Todos</option>
              <option value="true">Com Solar</option>
              <option value="false">Sem Solar</option>
            </select>
          </div>
          
          <button
            onClick={handleSearch}
            className="btn-primary"
          >
            <MagnifyingGlassIcon className="w-5 h-5 mr-2" />
            Carregar Pontos
          </button>
          
          {mapaData?.pontos && (
            <span className="text-sm text-gray-600">
              {mapaData.pontos.length} pontos no mapa
            </span>
          )}
        </div>
      </div>
      
      {/* Mapa e Street View */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Mapa */}
        <div className="card relative overflow-hidden">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100 z-10">
              <div className="text-center">
                <span className="spinner w-8 h-8 text-primary-600" />
                <p className="mt-2 text-gray-600">Carregando mapa...</p>
              </div>
            </div>
          )}
          
          {mapError && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100 z-10">
              <div className="text-center p-8">
                <MapPinIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Mapa não disponível
                </h3>
                <p className="text-gray-600 max-w-sm">
                  {mapError}
                </p>
                <p className="text-sm text-gray-500 mt-4">
                  Adicione <code className="bg-gray-200 px-1 rounded">VITE_GOOGLE_MAPS_API_KEY</code> ao arquivo .env do frontend
                </p>
              </div>
            </div>
          )}
          
          <div ref={mapRef} className="w-full h-full min-h-[400px]" />
        </div>
        
        {/* Street View */}
        <div className="card relative overflow-hidden">
          {!showStreetView && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100 z-10">
              <div className="text-center p-8">
                <EyeIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Street View
                </h3>
                <p className="text-gray-600 max-w-sm">
                  Clique em um ponto no mapa e depois em "Ver Street View" para visualizar a vista da rua
                </p>
              </div>
            </div>
          )}
          
          {showStreetView && (
            <div className="absolute top-4 right-4 z-20 flex gap-2">
              <button
                onClick={closeStreetView}
                className="btn-outline bg-white shadow-lg"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
              <button
                onClick={() => {
                  if (selectedPoint) {
                    window.open(
                      `https://www.google.com/maps?q=${selectedPoint.latitude},${selectedPoint.longitude}&layer=c&cbll=${selectedPoint.latitude},${selectedPoint.longitude}`,
                      '_blank'
                    )
                  }
                }}
                className="btn-outline bg-white shadow-lg"
              >
                <ArrowsPointingOutIcon className="w-5 h-5" />
              </button>
            </div>
          )}
          
          <div ref={streetViewRef} className="w-full h-full min-h-[400px]" />
        </div>
      </div>
      
      {/* Info do ponto selecionado */}
      {selectedPoint && (
        <div className="card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-gray-900">{selectedPoint.titulo}</h3>
              <p className="text-sm text-gray-600">{selectedPoint.descricao}</p>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-gray-600">
                <strong>Lat:</strong> {selectedPoint.latitude.toFixed(6)}
              </span>
              <span className="text-gray-600">
                <strong>Lng:</strong> {selectedPoint.longitude.toFixed(6)}
              </span>
              <button
                onClick={() => openStreetView(selectedPoint)}
                className="btn-primary text-sm"
              >
                <EyeIcon className="w-4 h-4 mr-1" />
                Street View
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Legenda */}
      <div className="card p-4">
        <div className="flex items-center gap-6 text-sm">
          <span className="font-medium text-gray-700">Legenda:</span>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-blue-500" />
            <span className="text-gray-600">Sem geração solar</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-green-500" />
            <span className="text-gray-600">Com geração solar</span>
          </div>
        </div>
      </div>
    </div>
  )
}
