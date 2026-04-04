import { useEffect, useState } from 'react'
import { getIncidents, updateIncidentStatus, type Incident } from '../api'

export default function IntelligenceHub() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [filter, setFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all')

  const load = () => getIncidents().then(setIncidents).catch(console.error)

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t) }, [])

  const handleResolve = async (id: string) => {
    await updateIncidentStatus(id, 'resolved')
    load()
  }

  const filtered = filter === 'all' ? incidents : incidents.filter(i => i.risk_level === filter)

  const riskColor = (level: string) => ({ high: '#ff4444', medium: '#ffb68c', low: '#4caf50' }[level] || '#a38c80')

  const counts = {
    all: incidents.length,
    high: incidents.filter(i => i.risk_level === 'high').length,
    medium: incidents.filter(i => i.risk_level === 'medium').length,
    low: incidents.filter(i => i.risk_level === 'low').length,
  }

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Left: Threat list */}
      <aside style={{ width: 280, background: '#0e0e0f', borderRight: '1px solid rgba(85,67,57,0.1)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: 16, borderBottom: '1px solid rgba(85,67,57,0.1)' }}>
          <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 11, letterSpacing: '0.2em', color: '#ffb68c', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 6, height: 6, background: '#ffb68c', borderRadius: '50%' }} className="animate-pulse" />
            THREAT DETECTION ENGINE
          </h2>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {incidents.filter(i => i.status !== 'resolved').slice(0, 8).map(inc => (
            <div key={inc.id} style={{
              background: '#201f20', padding: 12,
              borderLeft: `2px solid ${riskColor(inc.risk_level)}`
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#dcc1b4' }}>
                  {new Date(inc.created_at).toLocaleTimeString()}
                </span>
                <span style={{ fontSize: 9, padding: '2px 6px', background: `${riskColor(inc.risk_level)}20`, color: riskColor(inc.risk_level), border: `1px solid ${riskColor(inc.risk_level)}30`, fontFamily: 'Space Grotesk', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  {inc.risk_level}
                </span>
              </div>
              <div style={{ fontFamily: 'Space Grotesk', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>{inc.incident_type}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                <div>
                  <div style={{ fontSize: 9, color: '#a38c80', fontFamily: 'JetBrains Mono', textTransform: 'uppercase', marginBottom: 4 }}>Confidence</div>
                  <div style={{ display: 'flex', gap: 2 }}>
                    {[1,2,3,4,5].map(i => (
                      <div key={i} style={{ width: 16, height: 4, background: i <= Math.round(inc.confidence * 5) ? riskColor(inc.risk_level) : '#353436' }} />
                    ))}
                  </div>
                </div>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: riskColor(inc.risk_level) }}>{Math.round(inc.confidence * 100)}%</span>
              </div>
            </div>
          ))}
        </div>
        <div style={{ padding: 16, background: 'rgba(32,31,32,0.2)', fontSize: 10, fontFamily: 'JetBrains Mono', color: '#a38c80', borderTop: '1px solid rgba(85,67,57,0.1)' }}>
          SENSOR STATUS: NOMINAL<br />
          TOTAL INCIDENTS: {incidents.length}
        </div>
      </aside>

      {/* Center: Incident table */}
      <section style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '24px 32px', borderBottom: '1px solid rgba(85,67,57,0.1)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <h1 style={{ fontFamily: 'Space Grotesk', fontSize: 18, letterSpacing: '0.3em', color: '#ffb68c', textTransform: 'uppercase' }}>SIGNAL ANALYSIS HUB</h1>
              <p style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: '#a38c80', marginTop: 4 }}>REAL-TIME INCIDENT INTELLIGENCE FEED</p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['all', 'high', 'medium', 'low'] as const).map(f => (
                <button key={f} onClick={() => setFilter(f)} style={{
                  padding: '6px 12px', fontFamily: 'Space Grotesk', fontSize: 10,
                  textTransform: 'uppercase', letterSpacing: '0.1em', cursor: 'pointer',
                  background: filter === f ? (f === 'all' ? '#da7635' : riskColor(f)) : 'transparent',
                  color: filter === f ? '#131314' : '#a38c80',
                  border: `1px solid ${filter === f ? 'transparent' : 'rgba(85,67,57,0.3)'}`,
                  transition: 'all 0.2s'
                }}>
                  {f} ({counts[f]})
                </button>
              ))}
            </div>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '0 32px 32px' }}>
          {/* Table header */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr 1fr auto', gap: 16, padding: '12px 16px', borderBottom: '1px solid rgba(85,67,57,0.2)', marginTop: 16 }}>
            {['Type', 'Risk Level', 'Score', 'Confidence', 'Status', 'Time', 'Action'].map(h => (
              <span key={h} style={{ fontFamily: 'Space Grotesk', fontSize: 9, color: '#a38c80', textTransform: 'uppercase', letterSpacing: '0.15em' }}>{h}</span>
            ))}
          </div>

          {filtered.map(inc => (
            <div key={inc.id} style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr 1fr auto', gap: 16,
              padding: '14px 16px', borderBottom: '1px solid rgba(85,67,57,0.1)',
              borderLeft: `2px solid ${riskColor(inc.risk_level)}`,
              background: inc.risk_level === 'high' && inc.status !== 'resolved' ? 'rgba(255,68,68,0.03)' : 'transparent',
              transition: 'background 0.2s', alignItems: 'center'
            }}>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11, textTransform: 'uppercase', color: '#ffb68c' }}>{inc.incident_type}</span>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11, color: riskColor(inc.risk_level), fontWeight: 700, textTransform: 'uppercase' }}>{inc.risk_level}</span>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11 }}>{inc.risk_score.toFixed(4)}</span>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 11 }}>{Math.round(inc.confidence * 100)}%</span>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, textTransform: 'uppercase', color: inc.status === 'resolved' ? '#4caf50' : '#ffb68c' }}>{inc.status}</span>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#a38c80' }}>{new Date(inc.created_at).toLocaleTimeString()}</span>
              {inc.status !== 'resolved' ? (
                <button onClick={() => handleResolve(inc.id)} style={{
                  padding: '4px 10px', fontFamily: 'Space Grotesk', fontSize: 9,
                  textTransform: 'uppercase', letterSpacing: '0.1em', cursor: 'pointer',
                  background: 'transparent', color: '#4caf50', border: '1px solid rgba(76,175,80,0.3)',
                  transition: 'all 0.2s', whiteSpace: 'nowrap'
                }}>Resolve</button>
              ) : (
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#4caf50' }}>✓ DONE</span>
              )}
            </div>
          ))}

          {filtered.length === 0 && (
            <div style={{ padding: 48, textAlign: 'center', fontFamily: 'JetBrains Mono', fontSize: 12, color: '#4caf50', letterSpacing: '0.2em' }}>
              NO INCIDENTS FOUND
            </div>
          )}
        </div>
      </section>

      {/* Right: Stats */}
      <aside style={{ width: 280, background: '#0e0e0f', borderLeft: '1px solid rgba(85,67,57,0.1)', display: 'flex', flexDirection: 'column', padding: 24, gap: 24 }}>
        <div>
          <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 11, letterSpacing: '0.2em', color: '#ffb68c', textTransform: 'uppercase', marginBottom: 16 }}>GEOSPATIAL INTEL</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { label: 'Total Incidents', value: incidents.length },
              { label: 'Active', value: incidents.filter(i => i.status !== 'resolved').length },
              { label: 'Resolved', value: incidents.filter(i => i.status === 'resolved').length },
              { label: 'High Risk', value: incidents.filter(i => i.risk_level === 'high').length },
            ].map(s => (
              <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'JetBrains Mono', fontSize: 10 }}>
                <span style={{ color: '#a38c80', textTransform: 'uppercase' }}>{s.label}</span>
                <span style={{ color: '#e5e2e3' }}>{s.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ borderTop: '1px solid rgba(85,67,57,0.2)', paddingTop: 24 }}>
          <h3 style={{ fontFamily: 'Space Grotesk', fontSize: 10, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase', marginBottom: 12 }}>Risk Distribution</h3>
          {(['high', 'medium', 'low'] as const).map(level => {
            const count = incidents.filter(i => i.risk_level === level).length
            const pct = incidents.length ? Math.round(count / incidents.length * 100) : 0
            return (
              <div key={level} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: 'JetBrains Mono', marginBottom: 4 }}>
                  <span style={{ color: riskColor(level), textTransform: 'uppercase' }}>{level}</span>
                  <span style={{ color: '#a38c80' }}>{count} ({pct}%)</span>
                </div>
                <div style={{ height: 4, background: '#353436' }}>
                  <div style={{ height: '100%', background: riskColor(level), width: `${pct}%`, transition: 'width 0.5s ease' }} />
                </div>
              </div>
            )
          })}
        </div>

        {/* Encrypted data stream */}
        <div style={{ marginTop: 'auto', borderTop: '1px solid rgba(85,67,57,0.2)', paddingTop: 16 }}>
          <div style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#a38c80', lineHeight: 1.8 }}>
            <div style={{ color: '#ffb68c', marginBottom: 4, letterSpacing: '0.1em' }}>ENCRYPTED DATA STREAM</div>
            <div className="animate-pulse">0x4F 0x21 0xBC [COMM_LINK_ESTABLISHED]</div>
            <div style={{ opacity: 0.5 }}>TX_BUFFER: READY</div>
            <div style={{ opacity: 0.5 }}>SEC_LVL: 5</div>
          </div>
        </div>
      </aside>
    </div>
  )
}
