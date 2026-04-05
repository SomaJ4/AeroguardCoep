import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import type { Drone, Incident, DispatchLogRecord, NoFlyZone } from '../api'

interface Props {
  drones: Drone[]
  incidents: Incident[]
  dispatchLogs?: DispatchLogRecord[]
  noFlyZones?: NoFlyZone[]
}

const NFZ_COLORS: Record<string, string> = {
  hospital: '#ff6b6b',
  military: '#ff4444',
  airport: '#ff8800',
  stadium: '#ffcc00',
  industrial: '#cc88ff',
  university: '#44aaff',
}

function buildNFZGeoJSON(noFlyZones: NoFlyZone[]) {
  return {
    type: 'FeatureCollection' as const,
    features: noFlyZones.map(zone => ({
      type: 'Feature' as const,
      properties: { name: zone.name, reason: zone.reason, color: NFZ_COLORS[zone.reason] || '#ff4444' },
      geometry: {
        type: 'Polygon' as const,
        coordinates: [[...zone.polygon.map(p => [p.lng, p.lat] as [number, number]), [zone.polygon[0].lng, zone.polygon[0].lat] as [number, number]]],
      },
    })),
  }
}

function buildRoutesGeoJSON(dispatchLogs: DispatchLogRecord[], drones: Drone[]) {
  return {
    type: 'FeatureCollection' as const,
    features: dispatchLogs
      .filter(log => log.route_geojson?.coordinates?.length)
      .map(log => {
        const drone = drones.find(d => d.id === log.drone_id)
        const isOnScene = drone?.status === 'on_scene'
        const isEnRoute = drone?.status === 'en_route'
        const coords = isOnScene ? [...log.route_geojson!.coordinates].reverse() : log.route_geojson!.coordinates
        return {
          type: 'Feature' as const,
          properties: {
            color: isEnRoute ? '#ffb68c' : isOnScene ? '#65d3fe' : 'rgba(255,182,140,0.3)',
            width: isEnRoute || isOnScene ? 3 : 1,
          },
          geometry: { type: 'LineString' as const, coordinates: coords },
        }
      }),
  }
}

export default function TacticalMap3D({ drones, incidents, dispatchLogs = [], noFlyZones = [] }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])
  const styleLoadedRef = useRef(false)

  // Init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [73.9357, 18.5018],
      zoom: 13,
      pitch: 45,
      bearing: -20,
    })

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')

    map.on('load', () => {
      styleLoadedRef.current = true

      // Add NFZ source + layers
      map.addSource('nfz', { type: 'geojson', data: buildNFZGeoJSON(noFlyZones) })
      map.addLayer({ id: 'nfz-fill', type: 'fill', source: 'nfz', paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.2 } })
      map.addLayer({ id: 'nfz-line', type: 'line', source: 'nfz', paint: { 'line-color': ['get', 'color'], 'line-width': 1.5, 'line-dasharray': [3, 2], 'line-opacity': 0.8 } })

      // Add routes source + layer
      map.addSource('routes', { type: 'geojson', data: buildRoutesGeoJSON(dispatchLogs, drones) })
      map.addLayer({ id: 'routes-line', type: 'line', source: 'routes', paint: { 'line-color': ['get', 'color'], 'line-width': ['get', 'width'], 'line-dasharray': [4, 3] } })
    })

    mapRef.current = map

    return () => {
      styleLoadedRef.current = false
      map.remove()
      mapRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Update NFZ data when zones change
  useEffect(() => {
    const map = mapRef.current
    if (!map || !styleLoadedRef.current) return
    const src = map.getSource('nfz') as maplibregl.GeoJSONSource | undefined
    src?.setData(buildNFZGeoJSON(noFlyZones))
  }, [noFlyZones])

  // Update routes data when logs/drones change
  useEffect(() => {
    const map = mapRef.current
    if (!map || !styleLoadedRef.current) return
    const src = map.getSource('routes') as maplibregl.GeoJSONSource | undefined
    src?.setData(buildRoutesGeoJSON(dispatchLogs, drones))
  }, [dispatchLogs, drones])

  // Update markers
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    drones.forEach(drone => {
      const color = drone.status === 'available' ? '#4caf50' : drone.status === 'en_route' ? '#ffb68c' : drone.status === 'on_scene' ? '#65d3fe' : '#a38c80'
      const el = document.createElement('div')
      el.style.cssText = `width:14px;height:14px;background:${color};border:2px solid rgba(255,255,255,0.4);box-shadow:0 0 12px ${color};transform:rotate(45deg);cursor:pointer;`
      const popup = new maplibregl.Popup({ offset: 12, closeButton: false })
        .setHTML(`<div style="font-family:monospace;font-size:11px;background:#201f20;color:#e5e2e3;padding:8px;min-width:140px"><b style="color:#ffb68c">${drone.name}</b><br>Status: ${drone.status.toUpperCase()}<br>Battery: ${Math.round(drone.battery_pct)}%</div>`)
      markersRef.current.push(new maplibregl.Marker({ element: el }).setLngLat([drone.lng, drone.lat]).setPopup(popup).addTo(map))
    })

    incidents.filter(i => i.status !== 'resolved').forEach(inc => {
      const droneOnScene = dispatchLogs.some(log => {
        const drone = drones.find(d => d.id === log.drone_id)
        return log.incident_id === inc.id && drone?.status === 'on_scene'
      })
      const color = droneOnScene ? '#65d3fe' : inc.risk_level === 'high' ? '#ff4444' : inc.risk_level === 'medium' ? '#ffb68c' : '#4caf50'
      const el = document.createElement('div')
      el.style.cssText = `width:${droneOnScene ? 20 : 14}px;height:${droneOnScene ? 20 : 14}px;background:${color};border-radius:50%;border:2px solid rgba(255,255,255,0.5);box-shadow:0 0 16px ${color};cursor:pointer;`
      const popup = new maplibregl.Popup({ offset: 12, closeButton: false })
        .setHTML(`<div style="font-family:monospace;font-size:11px;background:#201f20;color:#e5e2e3;padding:8px;min-width:140px"><b style="color:${color}">${droneOnScene ? '✓ DRONE ON SCENE' : inc.incident_type.toUpperCase()}</b><br>Risk: ${inc.risk_level.toUpperCase()}<br>Score: ${inc.risk_score.toFixed(4)}</div>`)
      markersRef.current.push(new maplibregl.Marker({ element: el }).setLngLat([inc.lng, inc.lat]).setPopup(popup).addTo(map))
    })
  }, [drones, incidents, dispatchLogs])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      <div style={{ position: 'absolute', bottom: 40, left: 16, display: 'flex', flexDirection: 'column', gap: 4, zIndex: 10 }}>
        {[{ label: '3D', pitch: 60 }, { label: '45°', pitch: 45 }, { label: 'TOP', pitch: 0 }].map(v => (
          <button key={v.label} onClick={() => mapRef.current?.easeTo({ pitch: v.pitch, duration: 500 })}
            style={{ padding: '4px 8px', fontFamily: 'Space Grotesk', fontSize: 9, textTransform: 'uppercase', letterSpacing: '0.1em', background: 'rgba(14,14,15,0.9)', color: '#ffb68c', border: '1px solid rgba(255,182,140,0.3)', cursor: 'pointer' }}>
            {v.label}
          </button>
        ))}
      </div>
    </div>
  )
}
