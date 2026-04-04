import { useEffect, useState } from 'react'
import { getDrones, getIncidents, getDispatchLogs, getNoFlyZones, type Drone, type Incident, type DispatchLogRecord, type NoFlyZone } from '../api'
import TacticalLeafletMap from '../components/TacticalLeafletMap'

export default function CommandOverview() {
  const [drones, setDrones] = useState<Drone[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [dispatchLogs, setDispatchLogs] = useState<DispatchLogRecord[]>([])
  const [noFlyZones, setNoFlyZones] = useState<NoFlyZone[]>([])

  useEffect(() => {
    const load = () => {
      getDrones().then(setDrones).catch(console.error)
      getIncidents().then(setIncidents).catch(console.error)
      getDispatchLogs().then(setDispatchLogs).catch(console.error)
    }
    getNoFlyZones().then(setNoFlyZones).catch(console.error)
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  const available = drones.filter(d => d.status === 'available').length
  const enRoute = drones.filter(d => d.status === 'en_route').length
  const activeIncidents = incidents.filter(i => i.status !== 'resolved')
  const highRisk = activeIncidents.filter(i => i.risk_level === 'high')
  const avgRisk = activeIncidents.length
    ? Math.round(activeIncidents.reduce((s, i) => s + i.risk_score, 0) / activeIncidents.length * 100)
    : 0

  const riskColor = avgRisk > 70 ? '#ff4444' : avgRisk > 40 ? '#ffb68c' : '#4caf50'
  const circumference = 2 * Math.PI * 70
  const dashOffset = circumference - (avgRisk / 100) * circumference

  return (
    <div style={{ display: 'flex', height: '100%', position: 'relative' }}>
      <div className="grid-overlay" style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} />

      {/* Left: Map area */}
      <section style={{ flex: 1, position: 'relative', background: '#0e0e0f', overflow: 'hidden' }}>
        <TacticalLeafletMap drones={drones} incidents={incidents} dispatchLogs={dispatchLogs} noFlyZones={noFlyZones} showRoutes={true} />

        {/* Header overlay on top of map */}
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 1000, background: 'linear-gradient(to bottom, rgba(19,19,20,0.9) 0%, transparent 100%)', padding: '16px 24px', pointerEvents: 'none' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ width: 8, height: 8, background: '#ffb68c' }} className="animate-pulse" />
            <h1 style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 300, letterSpacing: '0.15em', textTransform: 'uppercase' }}>
              CITY-WIDE INCIDENT COMMAND OVERVIEW
            </h1>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: '#a38c80', background: 'rgba(32,31,32,0.7)', padding: '3px 8px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>SEC_ALPHA_GRID_042</span>
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: '#a38c80', background: 'rgba(32,31,32,0.7)', padding: '3px 8px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>COORD: 18.5204° N, 73.8567° E</span>
          </div>
        </div>

        {/* Stats bottom left overlay */}
        <div style={{ position: 'absolute', bottom: 16, left: 16, display: 'flex', gap: 8, zIndex: 1000, pointerEvents: 'none' }}>
          {[
            { label: 'Active', value: activeIncidents.length, color: highRisk.length > 0 ? '#ff4444' : '#ffb68c' },
            { label: 'High Risk', value: highRisk.length, color: '#ff4444' },
            { label: 'Available', value: available, color: '#4caf50' },
            { label: 'En Route', value: enRoute, color: '#ffb68c' },
          ].map(s => (
            <div key={s.label} style={{ background: 'rgba(14,14,15,0.85)', border: '1px solid rgba(85,67,57,0.4)', padding: '8px 12px', minWidth: 64, textAlign: 'center' }}>
              <div style={{ fontSize: 8, fontFamily: 'Space Grotesk', color: '#a38c80', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 2 }}>{s.label}</div>
              <div style={{ fontSize: 18, fontFamily: 'JetBrains Mono', color: s.color, fontWeight: 700 }}>{s.value}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Right panel */}
      <section style={{ width: 400, background: '#0e0e0f', borderLeft: '1px solid rgba(85,67,57,0.3)', overflowY: 'auto', padding: 32, display: 'flex', flexDirection: 'column', gap: 32 }}>

        {/* Threat gauge */}
        <div>
          <h3 style={{ fontFamily: 'Space Grotesk', fontSize: 10, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase', marginBottom: 16 }}>Threat Assessment</h3>
          <div style={{ background: '#201f20', padding: 24, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{ position: 'relative', width: 160, height: 160 }}>
              <svg width="160" height="160" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="80" cy="80" r="70" fill="none" stroke="#353436" strokeWidth="4" />
                <circle cx="80" cy="80" r="70" fill="none" stroke={riskColor}
                  strokeWidth="6" strokeDasharray={circumference} strokeDashoffset={dashOffset}
                  style={{ transition: 'stroke-dashoffset 0.5s ease' }} />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: 36, fontWeight: 300, color: riskColor }}>{avgRisk}</span>
                <span style={{ fontFamily: 'Space Grotesk', fontSize: 9, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase' }}>RISK INDEX</span>
              </div>
            </div>
            <div style={{ marginTop: 16, background: `${riskColor}1a`, border: `1px solid ${riskColor}33`, padding: '8px 24px', width: '100%', textAlign: 'center' }}>
              <span style={{ fontFamily: 'Space Grotesk', fontSize: 14, fontWeight: 500, letterSpacing: '0.2em', color: riskColor }}>
                LEVEL: {avgRisk > 70 ? 'CRITICAL' : avgRisk > 40 ? 'ELEVATED' : 'NOMINAL'}
              </span>
            </div>
          </div>
        </div>

        {/* Response readiness */}
        <div>
          <h3 style={{ fontFamily: 'Space Grotesk', fontSize: 10, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase', marginBottom: 16 }}>Response Readiness</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
            {[
              { label: 'Drones', value: drones.length },
              { label: 'Available', value: available },
              { label: 'En Route', value: enRoute },
            ].map(s => (
              <div key={s.label} style={{ background: '#1c1b1c', padding: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <span style={{ fontFamily: 'Space Grotesk', fontSize: 9, color: '#a38c80', textTransform: 'uppercase' }}>{s.label}</span>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: 20, fontWeight: 700 }}>{s.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent incidents */}
        <div>
          <h3 style={{ fontFamily: 'Space Grotesk', fontSize: 10, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase', marginBottom: 16 }}>Recent Incidents</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {incidents.slice(0, 5).map(inc => (
              <div key={inc.id} style={{
                background: '#1c1b1c', padding: '12px 16px',
                borderLeft: `2px solid ${inc.risk_level === 'high' ? '#ff4444' : inc.risk_level === 'medium' ? '#ffb68c' : '#4caf50'}`,
                display: 'flex', justifyContent: 'space-between', alignItems: 'center'
              }}>
                <div>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#ffb68c', textTransform: 'uppercase' }}>{inc.incident_type}</div>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#a38c80', marginTop: 2 }}>
                    {new Date(inc.created_at).toLocaleTimeString()}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: inc.risk_level === 'high' ? '#ff4444' : '#ffb68c', fontWeight: 700 }}>
                    {inc.risk_level.toUpperCase()}
                  </div>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#a38c80' }}>{inc.risk_score.toFixed(3)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
