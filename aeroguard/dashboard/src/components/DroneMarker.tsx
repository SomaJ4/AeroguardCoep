import { useEffect, useRef } from 'react'
import { Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import lottie from 'lottie-web'
import type { Drone } from '../api'
import droneAnimationData from '../assets/drone.json'

interface Props {
  drone: Drone
  selected: boolean
  onSelect: (id: string) => void
}

const STATUS_COLORS: Record<string, string> = {
  available: '#4caf50',
  en_route:  '#ffb68c',
  on_scene:  '#65d3fe',
  charging:  '#a38c80',
}

// One stable DivIcon per drone id — never recreated
const iconRegistry: Record<string, L.DivIcon> = {}

function getOrCreateIcon(droneId: string): L.DivIcon {
  if (iconRegistry[droneId]) return iconRegistry[droneId]
  const containerId = `drone-lottie-${droneId}`
  iconRegistry[droneId] = L.divIcon({
    className: '',
    html: `<div id="${containerId}" style="width:44px;height:44px;"></div>`,
    iconSize: [44, 44],
    iconAnchor: [22, 22],
  })
  return iconRegistry[droneId]
}

export default function DroneMarker({ drone, selected, onSelect }: Props) {
  const animRef = useRef<ReturnType<typeof lottie.loadAnimation> | null>(null)
  const mountedRef = useRef(false)
  const color = STATUS_COLORS[drone.status] || '#ffb68c'
  const icon = getOrCreateIcon(drone.id)
  const containerId = `drone-lottie-${drone.id}`

  useEffect(() => {
    // Wait for Leaflet to insert the DivIcon DOM node, then mount Lottie once
    const tryMount = () => {
      const el = document.getElementById(containerId)
      if (!el || mountedRef.current) return
      mountedRef.current = true
      animRef.current = lottie.loadAnimation({
        container: el,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        animationData: droneAnimationData,
      })
    }

    // Leaflet renders the icon slightly after React — small delay is reliable
    const timer = setTimeout(tryMount, 100)
    return () => clearTimeout(timer)
  }, [containerId])

  // Update glow color when status changes — don't remount animation
  useEffect(() => {
    const el = document.getElementById(containerId)
    if (el) {
      el.style.filter = `drop-shadow(0 0 ${selected ? 10 : 6}px ${color})`
      el.style.transform = selected ? 'scale(1.2)' : 'scale(1)'
      el.style.transition = 'transform 0.2s, filter 0.2s'
    }
  }, [drone.status, selected, color, containerId])

  return (
    <Marker
      position={[drone.lat, drone.lng]}
      icon={icon}
      eventHandlers={{ click: () => onSelect(drone.id) }}
      zIndexOffset={selected ? 1000 : 0}
    >
      <Popup>
        <div style={{
          fontFamily: 'JetBrains Mono', fontSize: 11,
          background: '#201f20', color: '#e5e2e3',
          padding: 10, minWidth: 160,
        }}>
          <div style={{ color, fontWeight: 700, marginBottom: 6, textTransform: 'uppercase' }}>
            {drone.name}
            {selected && (
              <span style={{ marginLeft: 8, fontSize: 9, background: 'rgba(255,182,140,0.2)', padding: '1px 6px', border: '1px solid rgba(255,182,140,0.3)', color: '#ffb68c' }}>
                SELECTED
              </span>
            )}
          </div>
          <div>Status: <span style={{ color, textTransform: 'uppercase' }}>{drone.status}</span></div>
          <div>Battery: {Math.round(drone.battery_pct)}%</div>
          <div>Speed: {drone.speed_kmh} km/h</div>
          <div style={{ color: '#a38c80', marginTop: 4, fontSize: 9 }}>
            {drone.lat.toFixed(4)}°N {drone.lng.toFixed(4)}°E
          </div>
        </div>
      </Popup>
    </Marker>
  )
}
