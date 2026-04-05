import { useEffect, useRef, useState } from 'react'
import { getCameras, type Camera } from '../api'

interface VideoSlot {
  file: File | null
  cameraId: string
  preview: string | null
  status: 'idle' | 'uploading' | 'success' | 'error'
  result: any | null
  error: string | null
}

const SLOT_COUNT = 6

function makeSlot(): VideoSlot {
  return { file: null, cameraId: '', preview: null, status: 'idle', result: null, error: null }
}

export default function VideoUpload() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [slots, setSlots] = useState<VideoSlot[]>(Array.from({ length: SLOT_COUNT }, makeSlot))
  const [uploading, setUploading] = useState(false)
  const [log, setLog] = useState<string[]>(['[SYSTEM] VIDEO ANALYSIS ENGINE READY', '[SYSTEM] AWAITING FEED INPUT'])
  const fileRefs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    getCameras().then(setCameras).catch(console.error)
  }, [])

  const addLog = (msg: string) => setLog(l => [...l.slice(-20), `[${new Date().toLocaleTimeString('en-US', { hour12: false })}] ${msg}`])

  const handleFileSelect = (idx: number, file: File) => {
    const preview = URL.createObjectURL(file)
    setSlots(s => s.map((slot, i) => i === idx ? { ...slot, file, preview, status: 'idle', result: null, error: null } : slot))
    addLog(`FEED ${String(idx + 1).padStart(2, '0')} — ${file.name} LOADED`)
  }

  const handleDrop = (idx: number, e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('video/')) handleFileSelect(idx, file)
  }

  const updateSlot = (idx: number, patch: Partial<VideoSlot>) =>
    setSlots(s => s.map((slot, i) => i === idx ? { ...slot, ...patch } : slot))

  const handleAnalyze = async () => {
    const active = slots.map((s, i) => ({ ...s, idx: i })).filter(s => s.file && s.cameraId)
    if (!active.length) return
    setUploading(true)
    addLog(`INITIATING BATCH ANALYSIS — ${active.length} FEED(S)`)

    const form = new FormData()
    active.forEach(s => { form.append('files', s.file!); form.append('camera_ids', s.cameraId) })
    active.forEach(s => updateSlot(s.idx, { status: 'uploading' }))

    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const res = await fetch(`${baseUrl}/upload/videos`, { method: 'POST', body: form })
      const data = await res.json()
      const items: any[] = data.items || []
      items.forEach((item, i) => {
        const slot = active[i]
        if (!slot) return
        if (item.status === 'success') {
          updateSlot(slot.idx, { status: 'success', result: item.result })
          addLog(`FEED ${String(slot.idx + 1).padStart(2, '0')} — ${item.result?.incident_type?.toUpperCase()} | RISK: ${item.result?.risk_level?.toUpperCase()}`)
        } else {
          updateSlot(slot.idx, { status: 'error', error: item.error })
          addLog(`FEED ${String(slot.idx + 1).padStart(2, '0')} — ANALYSIS FAILED`)
        }
      })
      addLog('BATCH COMPLETE')
    } catch (e: any) {
      active.forEach(s => updateSlot(s.idx, { status: 'error', error: e.message }))
      addLog(`ERROR: ${e.message}`)
    }
    setUploading(false)
  }

  const clearSlot = (idx: number) => {
    const slot = slots[idx]
    if (slot.preview) URL.revokeObjectURL(slot.preview)
    setSlots(s => s.map((sl, i) => i === idx ? makeSlot() : sl))
  }

  const activeCount = slots.filter(s => s.file).length
  const readyCount = slots.filter(s => s.file && s.cameraId).length
  const successCount = slots.filter(s => s.status === 'success').length

  const riskColor = (level: string) =>
    level === 'high' ? '#ff4444' : level === 'medium' ? '#ffb68c' : '#4caf50'

  return (
    <div style={{ display: 'flex', height: '100%', background: '#0e0e0f' }}>

      {/* Left status panel */}
      <aside style={{ width: 220, background: '#0e0e0f', borderRight: '1px solid rgba(85,67,57,0.3)', display: 'flex', flexDirection: 'column', padding: 20, gap: 20 }}>
        <div>
          <div style={{ fontSize: 9, fontFamily: 'Space Grotesk', letterSpacing: '0.2em', color: 'rgba(220,193,180,0.4)', textTransform: 'uppercase', marginBottom: 12 }}>Engine Status</div>
          <div style={{ background: '#1c1b1c', padding: 14, borderLeft: '2px solid #ffb68c' }}>
            <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', color: 'rgba(220,193,180,0.5)', textTransform: 'uppercase' }}>Detection Engine</div>
            <div style={{ fontSize: 13, fontFamily: 'JetBrains Mono', color: '#ffb68c', fontWeight: 700, marginTop: 4 }}>ACTIVE — V.4.2.0</div>
          </div>
        </div>

        <div style={{ background: '#1c1b1c', padding: 14 }}>
          <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', color: 'rgba(220,193,180,0.5)', textTransform: 'uppercase' }}>CV Nodes</div>
          <div style={{ fontSize: 13, fontFamily: 'JetBrains Mono', color: '#4caf50', fontWeight: 700, marginTop: 4 }}>ONLINE [12/12]</div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            { label: 'Feeds Loaded', value: activeCount, color: '#ffb68c' },
            { label: 'Ready', value: readyCount, color: '#4caf50' },
            { label: 'Analyzed', value: successCount, color: '#65d3fe' },
            { label: 'Cameras', value: cameras.length, color: 'rgba(220,193,180,0.6)' },
          ].map(s => (
            <div key={s.label} style={{ background: '#1c1b1c', padding: 10, textAlign: 'center' }}>
              <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', color: 'rgba(220,193,180,0.4)', textTransform: 'uppercase', marginBottom: 4 }}>{s.label}</div>
              <div style={{ fontSize: 18, fontFamily: 'JetBrains Mono', color: s.color, fontWeight: 700 }}>{s.value}</div>
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* System log */}
        <div>
          <div style={{ fontSize: 9, fontFamily: 'Space Grotesk', letterSpacing: '0.2em', color: 'rgba(220,193,180,0.4)', textTransform: 'uppercase', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 12, color: '#ffb68c' }}>terminal</span>
            System Log
          </div>
          <div style={{ background: '#0a0a0b', border: '1px solid rgba(85,67,57,0.2)', padding: 10, height: 160, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 3 }}>
            {log.map((l, i) => (
              <div key={i} style={{ fontFamily: 'JetBrains Mono', fontSize: 8, color: l.includes('ERROR') || l.includes('FAILED') ? '#ff4444' : l.includes('COMPLETE') || l.includes('SUCCESS') ? '#4caf50' : 'rgba(220,193,180,0.45)', lineHeight: 1.4 }}>{l}</div>
            ))}
          </div>
        </div>
      </aside>

      {/* Center: feed grid */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '12px 20px', borderBottom: '1px solid rgba(85,67,57,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ width: 8, height: 8, background: uploading ? '#ffb68c' : '#4caf50', borderRadius: '50%' }} className={uploading ? 'animate-pulse' : ''} />
            <span style={{ fontFamily: 'Space Grotesk', fontSize: 11, letterSpacing: '0.2em', color: '#dcc1b4', textTransform: 'uppercase' }}>
              {uploading ? 'ANALYZING FEEDS...' : 'VIDEO FEED ANALYSIS'}
            </span>
          </div>
          <button
            onClick={handleAnalyze}
            disabled={uploading || readyCount === 0}
            style={{
              padding: '8px 20px', fontFamily: 'Space Grotesk', fontSize: 10, textTransform: 'uppercase',
              letterSpacing: '0.15em', fontWeight: 700, cursor: uploading || readyCount === 0 ? 'not-allowed' : 'pointer',
              background: uploading || readyCount === 0 ? 'rgba(218,118,53,0.2)' : '#da7635',
              color: uploading || readyCount === 0 ? '#ffb68c' : '#1a0a00',
              border: '1px solid rgba(255,182,140,0.4)', transition: 'all 0.2s',
              display: 'flex', alignItems: 'center', gap: 8,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>radar</span>
            {uploading ? 'PROCESSING...' : `ANALYZE ${readyCount > 0 ? `(${readyCount})` : ''}`}
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gridTemplateRows: 'repeat(2, 1fr)', gap: 12 }}>
          {slots.map((slot, idx) => (
            <div
              key={idx}
              onDrop={e => handleDrop(idx, e)}
              onDragOver={e => e.preventDefault()}
              style={{
                background: '#111112', border: `1px solid ${slot.status === 'success' ? 'rgba(76,175,80,0.4)' : slot.status === 'error' ? 'rgba(255,68,68,0.4)' : slot.status === 'uploading' ? 'rgba(255,182,140,0.5)' : 'rgba(85,67,57,0.25)'}`,
                position: 'relative', display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 160,
                transition: 'border-color 0.3s',
              }}
            >
              {/* Feed label */}
              <div style={{ position: 'absolute', top: 8, left: 8, zIndex: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: slot.status === 'success' ? '#4caf50' : slot.status === 'error' ? '#ff4444' : slot.status === 'uploading' ? '#ffb68c' : 'rgba(220,193,180,0.3)' }} className={slot.status === 'uploading' ? 'animate-pulse' : ''} />
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#dcc1b4', background: 'rgba(0,0,0,0.7)', padding: '2px 6px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  FEED {String(idx + 1).padStart(2, '0')} — {slot.file ? slot.file.name.slice(0, 16) : cameras[idx]?.name || `SLOT ${idx + 1}`}
                </span>
              </div>

              {/* Clear button */}
              {slot.file && (
                <button onClick={() => clearSlot(idx)} style={{ position: 'absolute', top: 8, right: 8, zIndex: 10, background: 'rgba(0,0,0,0.7)', border: '1px solid rgba(255,68,68,0.4)', color: '#ff4444', width: 20, height: 20, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 12 }}>close</span>
                </button>
              )}

              {/* Video preview or drop zone */}
              {slot.preview ? (
                <video src={slot.preview} style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: slot.status === 'uploading' ? 0.5 : 1 }} muted loop autoPlay playsInline />
              ) : (
                <div
                  onClick={() => fileRefs.current[idx]?.click()}
                  style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', gap: 8, padding: 16 }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 28, color: 'rgba(220,193,180,0.2)' }}>video_file</span>
                  <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: 'rgba(220,193,180,0.3)', textTransform: 'uppercase', textAlign: 'center' }}>DROP VIDEO OR CLICK</span>
                </div>
              )}
              <input ref={el => { fileRefs.current[idx] = el }} type="file" accept="video/*" style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) handleFileSelect(idx, f) }} />

              {/* Result overlay */}
              {slot.status === 'success' && slot.result && (
                <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'linear-gradient(transparent, rgba(0,0,0,0.92))', padding: '20px 10px 8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                    <div>
                      <div style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: riskColor(slot.result.risk_level), fontWeight: 700, textTransform: 'uppercase' }}>{slot.result.incident_type}</div>
                      <div style={{ fontFamily: 'JetBrains Mono', fontSize: 8, color: 'rgba(220,193,180,0.5)', marginTop: 2 }}>Score: {slot.result.risk_score?.toFixed(3)}</div>
                    </div>
                    <div style={{ background: `${riskColor(slot.result.risk_level)}22`, border: `1px solid ${riskColor(slot.result.risk_level)}55`, padding: '3px 8px' }}>
                      <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: riskColor(slot.result.risk_level), fontWeight: 700 }}>{slot.result.risk_level?.toUpperCase()}</span>
                    </div>
                  </div>
                </div>
              )}

              {slot.status === 'uploading' && (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.5)' }}>
                  <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#ffb68c', textTransform: 'uppercase', letterSpacing: '0.1em' }}>ANALYZING...</span>
                </div>
              )}

              {slot.status === 'error' && (
                <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'rgba(255,68,68,0.15)', padding: '6px 10px', borderTop: '1px solid rgba(255,68,68,0.3)' }}>
                  <span style={{ fontFamily: 'JetBrains Mono', fontSize: 8, color: '#ff4444' }}>ERROR: {slot.error?.slice(0, 40)}</span>
                </div>
              )}

              {/* Camera selector */}
              <div style={{ padding: '6px 8px', background: 'rgba(0,0,0,0.6)', borderTop: '1px solid rgba(85,67,57,0.2)' }}>
                <select
                  value={slot.cameraId}
                  onChange={e => updateSlot(idx, { cameraId: e.target.value })}
                  style={{ width: '100%', background: '#1c1b1c', border: '1px solid rgba(85,67,57,0.3)', color: slot.cameraId ? '#ffb68c' : 'rgba(220,193,180,0.4)', fontFamily: 'JetBrains Mono', fontSize: 9, padding: '4px 6px', textTransform: 'uppercase', outline: 'none', cursor: 'pointer' }}
                >
                  <option value="">— ASSIGN CAMERA —</option>
                  {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: AI Risk panel */}
      <aside style={{ width: 260, background: '#0e0e0f', borderLeft: '1px solid rgba(85,67,57,0.3)', display: 'flex', flexDirection: 'column', padding: 20, gap: 20, overflowY: 'auto' }}>
        <div>
          <div style={{ fontSize: 9, fontFamily: 'Space Grotesk', letterSpacing: '0.2em', color: 'rgba(220,193,180,0.4)', textTransform: 'uppercase', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 12, color: '#ffb68c' }}>psychology</span>
            AI Risk Analysis
          </div>

          {/* Latest result highlight */}
          {(() => {
            const latest = [...slots].reverse().find(s => s.status === 'success' && s.result)
            if (!latest?.result) return (
              <div style={{ background: '#1c1b1c', padding: 16, textAlign: 'center' }}>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: 'rgba(220,193,180,0.3)', textTransform: 'uppercase' }}>Awaiting Analysis</span>
              </div>
            )
            const r = latest.result
            const color = riskColor(r.risk_level)
            return (
              <div style={{ background: '#1c1b1c', padding: 16, borderLeft: `2px solid ${color}` }}>
                <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', color: 'rgba(220,193,180,0.5)', textTransform: 'uppercase', marginBottom: 6 }}>Threat Level</div>
                <div style={{ fontSize: 22, fontFamily: 'Space Grotesk', color, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>{r.risk_level === 'high' ? 'CRITICAL' : r.risk_level === 'medium' ? 'ELEVATED' : 'NOMINAL'}</div>
                <div style={{ height: 4, background: '#353436', marginBottom: 8 }}>
                  <div style={{ height: '100%', background: color, width: `${Math.round(r.risk_score * 100)}%`, transition: 'width 0.5s' }} />
                </div>
                <div style={{ fontSize: 9, fontFamily: 'JetBrains Mono', color: 'rgba(220,193,180,0.5)' }}>{Math.round(r.risk_score * 100)}% confidence</div>
              </div>
            )
          })()}
        </div>

        {/* Per-feed results */}
        <div>
          <div style={{ fontSize: 9, fontFamily: 'Space Grotesk', letterSpacing: '0.2em', color: 'rgba(220,193,180,0.4)', textTransform: 'uppercase', marginBottom: 10 }}>Active Snapshots</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {slots.filter(s => s.status === 'success' && s.result).map((s, i) => {
              const r = s.result
              const color = riskColor(r.risk_level)
              return (
                <div key={i} style={{ background: '#1c1b1c', padding: '10px 12px', borderLeft: `2px solid ${color}55` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#ffb68c', textTransform: 'uppercase' }}>{r.incident_type}</span>
                    <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color, fontWeight: 700 }}>{r.risk_level?.toUpperCase()}</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
                    <div>
                      <div style={{ fontSize: 8, color: 'rgba(220,193,180,0.4)', fontFamily: 'JetBrains Mono' }}>SCORE</div>
                      <div style={{ fontSize: 10, color: '#e5e2e3', fontFamily: 'JetBrains Mono' }}>{r.risk_score?.toFixed(3)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 8, color: 'rgba(220,193,180,0.4)', fontFamily: 'JetBrains Mono' }}>SOURCE</div>
                      <div style={{ fontSize: 10, color: '#e5e2e3', fontFamily: 'JetBrains Mono', textTransform: 'uppercase' }}>{r.decision_source || 'AI'}</div>
                    </div>
                  </div>
                </div>
              )
            })}
            {slots.filter(s => s.status === 'success').length === 0 && (
              <div style={{ padding: 12, textAlign: 'center', fontFamily: 'JetBrains Mono', fontSize: 9, color: 'rgba(220,193,180,0.3)', textTransform: 'uppercase' }}>No results yet</div>
            )}
          </div>
        </div>
      </aside>
    </div>
  )
}
