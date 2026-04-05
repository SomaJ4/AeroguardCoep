import { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, Polygon, Circle, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Drone, Incident, DispatchLogRecord, NoFlyZone } from '../api'
import DroneMarker from './DroneMarker'

// Fix default marker icons
try {
  delete (L.Icon.Default.prototype as any)._getIconUrl
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  })
} catch (_) {
  // ignore icon setup errors
}

const incidentIcon = (level: string, droneOnScene = false) => L.divIcon({
  className: '',
  html: droneOnScene
    ? `<div style="position:relative;width:32px;height:32px;display:flex;align-items:center;justify-content:center;">
        <div style="position:absolute;width:32px;height:32px;border-radius:50%;border:2px solid #65d3fe;opacity:0.8;animation:ripple1 1.5s ease-out infinite;"></div>
        <div style="position:absolute;width:24px;height:24px;border-radius:50%;border:2px solid #65d3fe;opacity:0.6;animation:ripple1 1.5s ease-out 0.4s infinite;"></div>
        <div style="position:absolute;width:16px;height:16px;border-radius:50%;border:2px solid #65d3fe;opacity:0.4;animation:ripple1 1.5s ease-out 0.8s infinite;"></div>
        <div style="width:10px;height:10px;background:#65d3fe;border-radius:50%;box-shadow:0 0 12px rgba(101,211,254,0.9);position:relative;z-index:10;"></div>
       </div>`
    : `<div style="
        width:16px;height:16px;
        background:${level === 'high' ? '#ff4444' : level === 'medium' ? '#ffb68c' : '#4caf50'};
        border-radius:50%;
        border:2px solid rgba(255,255,255,0.5);
        box-shadow:0 0 16px ${level === 'high' ? 'rgba(255,68,68,0.8)' : 'rgba(255,182,140,0.6)'};
        animation:pulse 2s infinite;
      "></div>`,
  iconSize: droneOnScene ? [32, 32] : [16, 16],
  iconAnchor: droneOnScene ? [16, 16] : [8, 8],
})

function MapStyler() {
  const map = useMap()
  useEffect(() => {
    const container = map.getContainer()
    container.style.background = '#0e0e0f'
    const style = document.createElement('style')
    style.textContent = `
      .leaflet-tile { filter: invert(1) hue-rotate(180deg) brightness(0.7) saturate(0.5) !important; }
      @keyframes ripple1 { 0% { transform: scale(0.5); opacity: 0.8; } 100% { transform: scale(2); opacity: 0; } }
    `
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
      {(Array.isArray(noFlyZones) ? noFlyZones : []).map(zone => {
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
      {incidents.filter(i => i.status !== 'resolved').map(inc => {
        const droneOnScene = dispatchLogs.some(log => {
          const drone = drones.find(d => d.id === log.drone_id)
          return log.incident_id === inc.id && drone?.status === 'on_scene'
        })
        return (
          <Marker
            key={inc.id}
            position={[inc.lat, inc.lng]}
            icon={incidentIcon(inc.risk_level, droneOnScene)}
            eventHandlers={{ click: () => onSelectIncident?.(inc.id) }}
          >
            <Popup className="tactical-popup">
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: 11, background: '#201f20', color: '#e5e2e3', padding: 8, minWidth: 160 }}>
                <div style={{ color: droneOnScene ? '#65d3fe' : '#ffb68c', fontWeight: 700, marginBottom: 4, textTransform: 'uppercase' }}>
                  {droneOnScene ? '✓ DRONE ON SCENE' : inc.incident_type}
                </div>
                <div>Risk: <span style={{ color: inc.risk_level === 'high' ? '#ff4444' : '#ffb68c' }}>{inc.risk_level.toUpperCase()}</span></div>
                <div>Score: {inc.risk_score.toFixed(4)}</div>
                <div>Confidence: {Math.round(inc.confidence * 100)}%</div>
                <div style={{ color: '#a38c80', marginTop: 4, fontSize: 9 }}>{inc.lat.toFixed(4)}°N {inc.lng.toFixed(4)}°E</div>
              </div>
            </Popup>
          </Marker>
        )
      })}

      {/* Pulse ring on selected incident */}
      {selInc && (
        <Circle
          center={[selInc.lat, selInc.lng]}
          radius={300}
          pathOptions={{ color: '#ffb68c', fillColor: '#ffb68c', fillOpacity: 0.05, weight: 1, dashArray: '4' }}
        />
      )}

      {/* Drone markers — Lottie animated */}
      {drones.map(drone => (
        <DroneMarker
          key={drone.id}
          drone={drone}
          selected={selectedDroneId === drone.id}
          onSelect={id => onSelectDrone?.(id)}
        />
      ))}

      {/* Dispatch route polylines from actual dispatch logs */}
      {showRoutes && dispatchLogs.map(log => {
        if (!log.route_geojson?.coordinates?.length) return null
        const positions: [number, number][] = log.route_geojson.coordinates.map(
          ([lng, lat]) => [lat, lng]
        )
        const drone = drones.find(d => d.id === log.drone_id)
        const isEnRoute = drone?.status === 'en_route'
        const isOnScene = drone?.status === 'on_scene'

        if (isEnRoute) {
          // Show dashed orange outbound route
          return (
            <Polyline
              key={log.id}
              positions={positions}
              pathOptions={{ color: '#ffb68c', weight: 2, dashArray: '6 4', opacity: 0.9 }}
            />
          )
        }

        if (isOnScene) {
          // Show return route in teal (reversed path)
          const returnPositions = [...positions].reverse()
          return (
            <Polyline
              key={log.id}
              positions={returnPositions}
              pathOptions={{ color: '#65d3fe', weight: 2, dashArray: '6 4', opacity: 0.7 }}
            />
          )
        }

        // Completed/inactive — faded
        return (
          <Polyline
            key={log.id}
            positions={positions}
            pathOptions={{ color: 'rgba(255,182,140,0.2)', weight: 1, dashArray: '2 6', opacity: 0.3 }}
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

      {/* Drone launch point markers — shows where each drone started from */}
      {showRoutes && dispatchLogs.map(log => {
        if (!log.route_geojson?.coordinates?.length) return null
        const [startLng, startLat] = log.route_geojson.coordinates[0]
        const drone = drones.find(d => d.id === log.drone_id)
        const isActive = drone && (drone.status === 'en_route' || drone.status === 'on_scene')
        if (!isActive) return null
        const launchIcon = L.divIcon({
          className: '',
          html: `<div style="
            width:10px;height:10px;
            background:transparent;
            border:2px solid #ffb68c;
            border-radius:50%;
            box-shadow:0 0 8px rgba(255,182,140,0.6);
          "></div>`,
          iconSize: [10, 10],
          iconAnchor: [5, 5],
        })
        return (
          <Marker
            key={`launch-${log.id}`}
            position={[startLat, startLng]}
            icon={launchIcon}
          >
            <Popup>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: 11, background: '#201f20', color: '#e5e2e3', padding: 8 }}>
                <div style={{ color: '#ffb68c', fontWeight: 700 }}>{drone?.name ?? 'Drone'}</div>
                <div style={{ color: '#a38c80', fontSize: 9 }}>LAUNCH POINT</div>
              </div>
            </Popup>
          </Marker>
        )
      })}
    </MapContainer>
  )
}
