import { useState, useMemo } from 'react'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useQuery } from '@tanstack/react-query'
import { aneelApi } from '@/services/api'
import type { MapaResponse } from '@/types'
import toast from 'react-hot-toast'
import {
  MapPinIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'

// Ícones customizados para Leaflet
const createCustomIcon = (color: string) => L.divIcon({
  className: 'custom-marker',
  html: `<div style="
    width: 20px;
    height: 20px;
    background-color: ${color};
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  "></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -10],
})

const solarIcon = createCustomIcon('#22c55e')
const normalIcon = createCustomIcon('#3b82f6')

// Função para gerar link do Google Maps Street View
const getStreetViewUrl = (lat: number, lng: number) => {
  return `https://www.google.com/maps/@${lat},${lng},3a,75y,90t/data=!3m6!1e1!3m4!1s!2e0!7i16384!8i8192?entry=ttu`
}

export default function MapaPage() {
  // Filtros
  const [filtros, setFiltros] = useState({
    demanda_min: '',
    demanda_max: '',
    possui_solar: '',
  })
  
  // Carregar dados do mapa
  const { data: mapaData, refetch, isFetching } = useQuery<MapaResponse>({
    queryKey: ['mapa-dados', filtros],
    queryFn: () => aneelApi.mapa({
      demanda_min: filtros.demanda_min ? parseFloat(filtros.demanda_min) : undefined,
      demanda_max: filtros.demanda_max ? parseFloat(filtros.demanda_max) : undefined,
      possui_solar: filtros.possui_solar ? filtros.possui_solar === 'true' : undefined,
      limit: 2000,
    }),
    enabled: false,
  })

  // Calcular centro do mapa
  const mapCenter = useMemo(() => {
    if (!mapaData?.pontos || mapaData.pontos.length === 0) {
      return { lat: -15.7801, lng: -47.9292 } // Brasília
    }
    const lats = mapaData.pontos.map(p => p.latitude)
    const lngs = mapaData.pontos.map(p => p.longitude)
    return {
      lat: lats.reduce((a, b) => a + b, 0) / lats.length,
      lng: lngs.reduce((a, b) => a + b, 0) / lngs.length,
    }
  }, [mapaData])
  
  // Buscar dados
  const handleSearch = () => {
    refetch().then(() => {
      if (mapaData?.pontos) {
        toast.success(`${mapaData.pontos.length} pontos carregados`)
      }
    })
  }
  
  return (
    <div className="min-h-[calc(100vh-8rem)] flex flex-col space-y-4">
      {/* Header */}
      <div className="relative overflow-hidden rounded-xl md:rounded-2xl bg-gradient-to-r from-blue-700 via-blue-600 to-green-500 text-white p-4 md:p-6">
        <div className="relative z-10">
          <h1 className="text-xl md:text-3xl font-bold">🗺️ Mapa de Clientes</h1>
          <p className="text-sm md:text-lg text-white/90 mt-1">
            Visualize a localização dos clientes BDGD
          </p>
        </div>
        <div className="absolute -right-8 -top-8 h-24 md:h-32 w-24 md:w-32 rounded-full bg-white/10" />
      </div>
      
      {/* Filtros */}
      <div className="card p-3 md:p-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 md:gap-4">
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
          
          <div>
            <label className="label text-xs md:text-sm font-semibold">Solar</label>
            <select
              className="input text-sm"
              value={filtros.possui_solar}
              onChange={(e) => setFiltros({ ...filtros, possui_solar: e.target.value })}
            >
              <option value="">Todos</option>
              <option value="true">☀️ Com</option>
              <option value="false">Sem</option>
            </select>
          </div>
          
          <div className="col-span-2 sm:col-span-1 flex flex-col justify-end">
            <button
              onClick={handleSearch}
              disabled={isFetching}
              className="btn-primary text-sm md:text-base px-4 py-2 md:px-6 md:py-3 w-full"
            >
              {isFetching ? (
                <span className="spinner mr-1" />
              ) : (
                <MagnifyingGlassIcon className="w-4 h-4 md:w-5 md:h-5 mr-1 md:mr-2" />
              )}
              🔍 Buscar
            </button>
          </div>
        </div>
        
        {mapaData?.pontos && (
          <p className="text-sm md:text-base font-semibold text-primary-600 mt-3 text-center">
            📍 {mapaData.pontos.length} pontos no mapa
          </p>
        )}
      </div>
      
      {/* Mapa com Leaflet */}
      <div className="flex-1 card relative overflow-hidden" style={{ minHeight: 'clamp(350px, 50vh, 600px)' }}>
        {mapaData?.pontos && mapaData.pontos.length > 0 ? (
          <MapContainer
            center={[mapCenter.lat, mapCenter.lng]}
            zoom={mapaData.pontos.length === 1 ? 14 : 5}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {mapaData.pontos.map((ponto) => (
              <Marker
                key={ponto.id}
                position={[ponto.latitude, ponto.longitude]}
                icon={ponto.dados?.possui_solar ? solarIcon : normalIcon}
              >
                <Popup>
                  <div className="min-w-[250px]">
                    <h3 className="font-bold text-lg text-blue-800 mb-3">
                      📍 {ponto.titulo}
                    </h3>
                    {ponto.descricao && (
                      <p className="text-gray-600 mb-2">{ponto.descricao}</p>
                    )}
                    {ponto.dados && (
                      <div className="space-y-1 text-sm border-t pt-2">
                        <div className="flex justify-between border-b pb-1">
                          <span className="font-medium">Grupo Tarifário:</span>
                          <span>{String(ponto.dados.gru_tar || '-')}</span>
                        </div>
                        <div className="flex justify-between border-b pb-1">
                          <span className="font-medium">Demanda:</span>
                          <span className="font-semibold text-green-700">
                            {typeof ponto.dados.dem_cont === 'number' 
                              ? `${ponto.dados.dem_cont.toLocaleString('pt-BR')} kW`
                              : '- kW'}
                          </span>
                        </div>
                        <div className="flex justify-between border-b pb-1">
                          <span className="font-medium">Energia Máx:</span>
                          <span className="font-semibold text-blue-700">
                            {typeof ponto.dados.ene_max === 'number' 
                              ? `${ponto.dados.ene_max.toLocaleString('pt-BR')} kWh`
                              : '- kWh'}
                          </span>
                        </div>
                        <div className="flex justify-between pb-1">
                          <span className="font-medium">Solar:</span>
                          <span className={ponto.dados.possui_solar ? 'text-green-600' : 'text-red-500'}>
                            {ponto.dados.possui_solar ? '☀️ Sim' : '❌ Não'}
                          </span>
                        </div>
                      </div>
                    )}
                    <div className="mt-3 pt-2 border-t text-xs text-gray-500 text-center">
                      📌 {ponto.latitude.toFixed(6)}, {ponto.longitude.toFixed(6)}
                    </div>
                    <a
                      href={getStreetViewUrl(ponto.latitude, ponto.longitude)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-3 block w-full text-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
                    >
                      🚶 Abrir Street View
                    </a>
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        ) : (
          <div className="h-full flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
            <div className="text-center p-4 md:p-8">
              <MapPinIcon className="w-12 h-12 md:w-20 md:h-20 text-gray-300 mx-auto mb-3 md:mb-4" />
              <h3 className="text-lg md:text-2xl font-bold text-gray-700 mb-2">
                Nenhum ponto carregado
              </h3>
              <p className="text-sm md:text-base text-gray-500 max-w-md">
                Use os filtros e clique em <strong>"Buscar"</strong> para visualizar
              </p>
            </div>
          </div>
        )}
        
        {/* Legenda - responsiva */}
        {mapaData?.pontos && mapaData.pontos.length > 0 && (
          <div className="absolute bottom-2 left-2 md:bottom-4 md:left-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-2 md:p-3 text-xs md:text-sm z-[1000]">
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
  )
}
