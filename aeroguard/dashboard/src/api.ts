import axios from 'axios'

const api = axios.create({ baseURL: 'http://127.0.0.1:8000' })

export interface Drone {
  id: string
  name: string
  lat: number
  lng: number
  home_lat: number
  home_lng: number
  battery_pct: number
  status: 'available' | 'en_route' | 'on_scene' | 'charging'
  speed_kmh: number
  stream_url: string | null
}

export interface Incident {
  id: string
  camera_id: string
  incident_type: string
  risk_score: number
  confidence: number
  risk_level: string
  lat: number
  lng: number
  snapshot_url: string | null
  status: string
  created_at: string
}

export interface DispatchLog {
  dispatch_log_id: string
  drone_id: string
  incident_id: string
  eta_seconds: number
  route_geojson: { type: string; coordinates: [number, number][] } | null
}

export interface DispatchLogRecord {
  id: string
  drone_id: string
  incident_id: string
  eta_seconds: number
  route_geojson: { type: string; coordinates: [number, number][] } | null
  dispatched_at: string
  arrived_at: string | null
}

export interface NoFlyZone {
  id: string
  name: string
  reason: string
  polygon: { lat: number; lng: number }[]
  is_active: boolean
}

export const getDrones = () => api.get<Drone[]>('/drones').then(r => r.data)
export const getIncidents = () => api.get<Incident[]>('/incidents').then(r => r.data)
export const getDispatchLogs = () => api.get<DispatchLogRecord[]>('/drones/dispatch/logs').then(r => r.data)
export const getNoFlyZones = () => api.get<NoFlyZone[]>('/drones/no-fly-zones').then(r => r.data)
export const dispatchDrone = (incident_id: string, drone_id?: string) =>
  api.post<DispatchLog>('/drones/dispatch', { incident_id, drone_id }).then(r => r.data)
export const updateIncidentStatus = (id: string, status: string) =>
  api.patch(`/incidents/${id}/status`, { status }).then(r => r.data)
export const updateDroneStatus = (id: string, status: string) =>
  api.patch(`/drones/${id}/status`, { status }).then(r => r.data)
