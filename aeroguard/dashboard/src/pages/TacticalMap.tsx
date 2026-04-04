import { useEffect, useState } from 'react'
import { getDrones, getIncidents, dispatchDrone, getDispatchLogs, getNoFlyZones, type Drone, type Incident, type DispatchLogRecord, type NoFlyZone } from '../api'
import TacticalLeafletMap from '../components/TacticalLeafletMap'

export default function TacticalMap() {
  const [drones, setDrones] = useState<Drone[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [dispatchLogs, setDispatchLogs] = useState<DispatchLogRecord[]>([])
  const [noFlyZones, setNoFlyZones] = useState<NoFlyZone[]>([])
  const [selectedDrone, setSelectedDrone] = useState<string | null>(null)
  const [selectedIncident, setSelectedIncident] = useState<string | null>(null)
  const [dispatching, setDispatching] = useState(false)
  const [log, setLog] = useState<string[]>(['[SYSTEM] TACTICAL MAP ONLINE', '[SYSTEM] AWAITING DISPATCH COMMAND'])

  const load = () => {
    getDrones().then(d => { setDrones(d); if (!selectedDrone && d.find(x => x.status === 'available')) setSelectedDrone(d.find(x => x.status === 'available')!.id) }).catch(console.error)
    getIncidents().then(i => { setIncidents(i); if (!selectedIncident && i.find(x => x.status !== 'resolved')) setSelectedIncident(i.find(x => x.status !== 'resolved')!.id) }).catch(console.error)
    getDispatchLogs().then(setDispatchLogs).catch(console.error)
  }

  useEffect(() => {
    getNoFlyZones().then(setNoFlyZones).catch(console.error)
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  const handleDispatch = async () => {
    if (!selectedIncident) return
    setDispatching(true)
    const ts = new Date().toLocaleTimeString('en-US', { hour12: false })
    setLog(l => [...l, `[${ts}] INITIATING DISPATCH...`])
    try {
      const result = await dispatchDrone(selectedIncident, selectedDrone || undefined)
      setLog(l => [...l, `[${ts}] DRONE DISPATCHED — ETA: ${result.eta_seconds}s`])
      load()
    } catch (e: any) {
      setLog(l => [...l, `[${ts}] DISPATCH FAILED: ${e?.response?.data?.detail || e.message}`])
    }
    setDispatching(false)
  }

  const availableDrones = drones.filter(d => d.status === 'available')
  const activeIncidents = incidents.filter(i => i.status !== 'resolved')
  const selDrone = drones.find(d => d.id === selectedDrone)
  const selInc = incidents.find(i => i.id === selectedIncident)

  const statusColor = (s: string) => ({ available: '#4caf50', en_route: '#ffb68c', on_scene: '#65d3fe', charging: '#a38c80' }[s] || '#a38c80')

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Left: Drone list */}
      <section style={{ width: 300, background: '#1c1b1c', borderRight: '1px solid rgba(85,67,57,0.1)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '16px', borderBottom: '1px solid rgba(85,67,57,0.2)', background: 'rgba(14,14,15,0.5)' }}>
          <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 11, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase', fontWeight: 700 }}>Available Drone Units</h2>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: 'rgba(220,193,180,0.4)' }}>TOTAL: {drones.length}</span>
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: '#ffb68c' }}>AVAIL: {availableDrones.length}</span>
          </div>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {drones.map(drone => (
            <div key={drone.id} onClick={() => drone.status === 'available' && setSelectedDrone(drone.id)}
              style={{
                background: selectedDrone === drone.id ? 'rgba(255,182,140,0.1)' : '#201f20',
                borderLeft: `2px solid ${selectedDrone === drone.id ? '#ffb68c' : 'transparent'}`,
                padding: 12, cursor: drone.status === 'available' ? 'pointer' : 'default',
                opacity: drone.status === 'available' ? 1 : 0.5, transition: 'all 0.2s'
              }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 12, fontWeight: 700, color: selectedDrone === drone.id ? '#ffb68c' : '#e5e2e3' }}>
                    {drone.name}
                    {selectedDrone === drone.id && <span style={{ marginLeft: 8, fontSize: 9, background: 'rgba(255,182,140,0.2)', padding: '1px 6px', border: '1px solid rgba(255,182,140,0.3)', color: '#ffb68c' }}>SELECTED</span>}
                  </div>
                  <div style={{ fontSize: 9, fontFamily: 'Space Grotesk', letterSpacing: '0.1em', color: '#dcc1b4', marginTop: 4, textTransform: 'uppercase' }}>X-4 SCOUT</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 12, color: drone.battery_pct > 50 ? '#4caf50' : '#ffb68c' }}>{Math.round(drone.battery_pct)}%</div>
                  <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', color: 'rgba(220,193,180,0.4)' }}>BATTERY</div>
                </div>
              </div>
              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div>
                  <div style={{ fontSize: 9, color: 'rgba(220,193,180,0.6)', fontFamily: 'JetBrains Mono' }}>STATUS</div>
                  <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: statusColor(drone.status), textTransform: 'uppercase' }}>{drone.status}</div>
                </div>
                <div>
                  <div style={{ fontSize: 9, color: 'rgba(220,193,180,0.6)', fontFamily: 'JetBrains Mono' }}>SPEED</div>
                  <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono' }}>{drone.speed_kmh} km/h</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Center: Map */}
      <section style={{ flex: 1, position: 'relative', background: '#0e0e0f', overflow: 'hidden' }}>
        <TacticalLeafletMap
          drones={drones}
          incidents={incidents}
          dispatchLogs={dispatchLogs}
          noFlyZones={noFlyZones}
          selectedDroneId={selectedDrone}
          selectedIncidentId={selectedIncident}
          onSelectDrone={setSelectedDrone}
          onSelectIncident={setSelectedIncident}
          showRoutes={true}
        />
      </section>

      {/* Right: AI Decision + Dispatch */}
      <section style={{ width: 360, background: '#1c1b1c', borderLeft: '1px solid rgba(85,67,57,0.1)', display: 'flex', flexDirection: 'column', padding: 24, gap: 24 }}>
        <div>
          <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 11, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase', fontWeight: 700, marginBottom: 16 }}>Select Incident</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {activeIncidents.slice(0, 4).map(inc => (
              <div key={inc.id} onClick={() => setSelectedIncident(inc.id)} style={{
                background: selectedIncident === inc.id ? 'rgba(255,182,140,0.1)' : '#201f20',
                borderLeft: `2px solid ${selectedIncident === inc.id ? '#ffb68c' : inc.risk_level === 'high' ? '#ff4444' : '#a38c80'}`,
                padding: '10px 12px', cursor: 'pointer', transition: 'all 0.2s'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#ffb68c', textTransform: 'uppercase' }}>{inc.incident_type}</span>
                  <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: inc.risk_level === 'high' ? '#ff4444' : '#ffb68c', fontWeight: 700 }}>{inc.risk_level.toUpperCase()}</span>
                </div>
                <div style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#a38c80', marginTop: 4 }}>Score: {inc.risk_score.toFixed(4)}</div>
              </div>
            ))}
            {activeIncidents.length === 0 && (
              <div style={{ padding: 16, textAlign: 'center', fontFamily: 'JetBrains Mono', fontSize: 10, color: '#4caf50' }}>NO ACTIVE INCIDENTS</div>
            )}
          </div>
        </div>

        {/* AI metrics */}
        <div>
          <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 11, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase', fontWeight: 700, marginBottom: 16 }}>AI Decision Logic</h2>
          {[
            { label: 'Distance Weight', value: 92 },
            { label: 'Battery Level', value: selDrone ? Math.round(selDrone.battery_pct) : 0 },
            { label: 'Airspace Verified', value: 100 },
            { label: 'Risk Score', value: selInc ? Math.round(selInc.risk_score * 100) : 0 },
          ].map(m => (
            <div key={m.label} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'JetBrains Mono', marginBottom: 4 }}>
                <span style={{ color: 'rgba(220,193,180,0.6)', textTransform: 'uppercase' }}>{m.label}</span>
                <span style={{ color: '#ffb68c' }}>{m.value}%</span>
              </div>
              <div style={{ height: 4, background: '#353436' }}>
                <div style={{ height: '100%', background: '#ffb68c', width: `${m.value}%`, transition: 'width 0.5s ease' }} />
              </div>
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Dispatch button */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button onClick={handleDispatch} disabled={dispatching || !selectedIncident || availableDrones.length === 0}
            style={{
              width: '100%', background: dispatching ? 'rgba(218,118,53,0.3)' : '#da7635',
              color: '#481d00', padding: '16px', fontFamily: 'Space Grotesk',
              textTransform: 'uppercase', letterSpacing: '0.2em', fontSize: 13, fontWeight: 700,
              border: '1px solid rgba(255,182,140,0.5)', cursor: dispatching ? 'wait' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              transition: 'all 0.2s', opacity: (!selectedIncident || availableDrones.length === 0) ? 0.5 : 1
            }}>
            <span className="material-symbols-outlined">send</span>
            {dispatching ? 'DISPATCHING...' : 'CONFIRM DRONE DISPATCH'}
          </button>
        </div>

        {/* Command log */}
        <div style={{ background: '#0e0e0f', border: '1px solid rgba(85,67,57,0.2)', padding: 12, maxHeight: 120, overflowY: 'auto' }}>
          {log.slice(-6).map((l, i) => (
            <div key={i} style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: l.includes('FAILED') ? '#ff4444' : l.includes('DISPATCHED') ? '#4caf50' : 'rgba(220,193,180,0.5)', marginBottom: 2 }}>{l}</div>
          ))}
        </div>
      </section>
    </div>
  )
}
