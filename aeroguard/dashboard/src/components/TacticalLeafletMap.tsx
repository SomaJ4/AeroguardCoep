import { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, Polygon, Circle, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Drone, Incident, DispatchLogRecord, NoFlyZone } from '../api'

// Fix default marker icons
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const droneIcon = (status: string) => L.divIcon({
  className: '',
  html: `<div style="
    width:14px;height:14px;
    background:${status === 'available' ? '#4caf50' : status === 'en_route' ? '#ffb68c' : status === 'on_scene' ? '#65d3fe' : '#a38c80'};
    border:2px solid rgba(255,255,255,0.4);
    box-shadow:0 0 12px ${status === 'en_route' ? 'rgba(255,182,140,0.8)' : 'rgba(76,175,80,0.6)'};
    transform:rotate(45deg);
  "></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
})

const incidentIcon = (level: string) => L.divIcon({
  className: '',
  html: `<div style="
    width:16px;height:16px;
    background:${level === 'high' ? '#ff4444' : level === 'medium' ? '#ffb68c' : '#4caf50'};
    border-radius:50%;
    border:2px solid rgba(255,255,255,0.5);
    box-shadow:0 0 16px ${level === 'high' ? 'rgba(255,68,68,0.8)' : 'rgba(255,182,140,0.6)'};
    animation:pulse 2s infinite;
  "></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
})

function MapStyler() {
  const map = useMap()
  useEffect(() => {
    const container = map.getContainer()
    container.style.background = '#0e0e0f'
    const style = document.createElement('style')
    style.textContent = `.leaflet-tile { filter: invert(1) hue-rotate(180deg) brightness(0.7) saturate(0.5) !important; }`
    document.head.appendChild(style)
    return () => { document.head.removeChild(style) }
  }, [map])
  return null
}

interface Props {
  drones: Drone[]
  incidents: Incident[]
  dispatchLogs?: DispatchLogRecord[]
  noFlyZones?: NoFlyZone[]
  selectedDroneId?: string | null
  selectedIncidentId?: string | null
  onSelectDrone?: (id: string) => void
  onSelectIncident?: (id: string) => void
  showRoutes?: boolean
}

export default function TacticalLeafletMap({
  drones, incidents, dispatchLogs = [], noFlyZones = [], selectedDroneId, selectedIncidentId,
  onSelectDrone, onSelectIncident, showRoutes = true
}: Props) {
  // Center on Pune (where the cameras are)
  const center: [number, number] = [18.5018, 73.9357]

  const selDrone = drones.find(d => d.id === selectedDroneId)
  const selInc = incidents.find(i => i.id === selectedIncidentId)

  return (
    <MapContainer
      center={center}
      zoom={13}
      style={{ width: '100%', height: '100%', background: '#0e0e0f' }}
      zoomControl={false}
    >
      <MapStyler />
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution=""
      />

      {/* No-fly zone polygons */}
      {noFlyZones.map(zone => {
        const positions: [number, number][] = zone.polygon.map(p => [p.lat, p.lng])
        const color = zone.reason === 'hospital' ? '#ff6b6b'
          : zone.reason === 'military' ? '#ff4444'
          : zone.reason === 'airport' ? '#ff8800'
          : zone.reason === 'stadium' ? '#ffcc00'
          : zone.reason === 'industrial' ? '#cc88ff'
          : zone.reason === 'university' ? '#44aaff'
          : '#ff4444'
        return (
          <Polygon
            key={zone.id}
            positions={positions}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: 0.15,
              weight: 1.5,
              dashArray: '4 3',
              opacity: 0.7,
            }}
          >
            <Tooltip sticky>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: 11 }}>
                <div style={{ fontWeight: 700, color }}>{zone.name}</div>
                <div style={{ color: '#888', textTransform: 'uppercase', fontSize: 9 }}>NO-FLY: {zone.reason}</div>
              </div>
            </Tooltip>
          </Polygon>
        )
      })}

      {/* Incident markers */}
      {incidents.filter(i => i.status !== 'resolved').map(inc => (
        <Marker
          key={inc.id}
          position={[inc.lat, inc.lng]}
          icon={incidentIcon(inc.risk_level)}
          eventHandlers={{ click: () => onSelectIncident?.(inc.id) }}
        >
          <Popup className="tactical-popup">
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: 11, background: '#201f20', color: '#e5e2e3', padding: 8, minWidth: 160 }}>
              <div style={{ color: '#ffb68c', fontWeight: 700, marginBottom: 4, textTransform: 'uppercase' }}>{inc.incident_type}</div>
              <div>Risk: <span style={{ color: inc.risk_level === 'high' ? '#ff4444' : '#ffb68c' }}>{inc.risk_level.toUpperCase()}</span></div>
              <div>Score: {inc.risk_score.toFixed(4)}</div>
              <div>Confidence: {Math.round(inc.confidence * 100)}%</div>
              <div style={{ color: '#a38c80', marginTop: 4, fontSize: 9 }}>{inc.lat.toFixed(4)}°N {inc.lng.toFixed(4)}°E</div>
            </div>
          </Popup>
        </Marker>
      ))}

      {/* Pulse ring on selected incident */}
      {selInc && (
        <Circle
          center={[selInc.lat, selInc.lng]}
          radius={300}
          pathOptions={{ color: '#ffb68c', fillColor: '#ffb68c', fillOpacity: 0.05, weight: 1, dashArray: '4' }}
        />
      )}

      {/* Drone markers */}
      {drones.map(drone => (
        <Marker
          key={drone.id}
          position={[drone.lat, drone.lng]}
          icon={droneIcon(drone.status)}
          eventHandlers={{ click: () => onSelectDrone?.(drone.id) }}
        >
          <Popup>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: 11, background: '#201f20', color: '#e5e2e3', padding: 8, minWidth: 160 }}>
              <div style={{ color: '#ffb68c', fontWeight: 700, marginBottom: 4 }}>{drone.name}</div>
              <div>Status: <span style={{ color: drone.status === 'available' ? '#4caf50' : '#ffb68c', textTransform: 'uppercase' }}>{drone.status}</span></div>
              <div>Battery: {Math.round(drone.battery_pct)}%</div>
              <div>Speed: {drone.speed_kmh} km/h</div>
            </div>
          </Popup>
        </Marker>
      ))}

      {/* Dispatch route polylines from actual dispatch logs */}
      {showRoutes && dispatchLogs.map(log => {
        if (!log.route_geojson?.coordinates?.length) return null
        // GeoJSON coords are [lng, lat] — Leaflet needs [lat, lng]
        const positions: [number, number][] = log.route_geojson.coordinates.map(
          ([lng, lat]) => [lat, lng]
        )
        const drone = drones.find(d => d.id === log.drone_id)
        const isActive = drone && (drone.status === 'en_route' || drone.status === 'on_scene')
        return (
          <Polyline
            key={log.id}
            positions={positions}
            pathOptions={{
              color: isActive ? '#ffb68c' : 'rgba(255,182,140,0.3)',
              weight: isActive ? 2 : 1,
              dashArray: isActive ? '6 4' : '2 6',
              opacity: isActive ? 0.9 : 0.4,
            }}
          />
        )
      })}

      {/* Fallback: dashed line from selected drone to selected incident when no log route */}
      {showRoutes && selDrone && selInc && dispatchLogs.length === 0 && (
        <Polyline
          positions={[[selDrone.lat, selDrone.lng], [selInc.lat, selInc.lng]]}
          pathOptions={{ color: '#ffb68c', weight: 2, dashArray: '6 4', opacity: 0.7 }}
        />
      )}
    </MapContainer>
  )
}
