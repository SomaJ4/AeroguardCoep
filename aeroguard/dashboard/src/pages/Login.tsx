import { useState, useEffect } from 'react'

interface Props {
  onLogin: () => void
}

const HARDCODED_USER = 'admin'
const HARDCODED_PASS = '123'

export default function Login({ onLogin }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [sliding, setSliding] = useState(false)
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (username === HARDCODED_USER && password === HARDCODED_PASS) {
      setError('')
      setSliding(true)
      setTimeout(onLogin, 600)
    } else {
      setError('INVALID CREDENTIALS — ACCESS DENIED')
    }
  }

  const ts = time.toLocaleTimeString('en-US', { hour12: false })
  const ds = time.toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' })

  return (
    <div style={{
      position: 'fixed', inset: 0, overflow: 'hidden',
      background: '#0a0a0b',
      transform: sliding ? 'translateY(-100%)' : 'translateY(0)',
      transition: sliding ? 'transform 0.6s cubic-bezier(0.76, 0, 0.24, 1)' : 'none',
      zIndex: 100,
    }}>
      {/* Animated background */}
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
        {/* Video bg — place bg.mp4 in public/ to activate */}
        <video
          autoPlay muted loop playsInline
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 0.65 }}
          onError={e => (e.currentTarget.style.display = 'none')}
        >
          <source src="/bgvideoscouts.mp4" type="video/mp4" />
        </video>

        {/* Tactical grid overlay */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,182,140,0.08) 1px, transparent 0)',
          backgroundSize: '40px 40px',
        }} />

        {/* Scan line sweep */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'repeating-linear-gradient(to bottom, transparent 0px, transparent 3px, rgba(255,182,140,0.12) 3px, rgba(255,182,140,0.12) 4px)',
          backgroundSize: '100% 4px',
          animation: 'scanline 6s linear infinite',
        }} />

        {/* Vignette */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.85) 100%)',
        }} />

        {/* Left gradient */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(to right, rgba(10,10,11,0.95) 0%, rgba(10,10,11,0.6) 55%, rgba(10,10,11,0.2) 100%)',
        }} />
      </div>

      <style>{`
        @keyframes scanline {
          0% { background-position: 0 0; }
          100% { background-position: 0 100vh; }
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(76,175,80,0.6); }
          50% { opacity: 0.7; box-shadow: 0 0 0 6px rgba(76,175,80,0); }
        }
        @keyframes blink {
          0%, 100% { opacity: 1; } 50% { opacity: 0; }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .login-field {
          width: 100%;
          background: transparent;
          border: none;
          border-bottom: 1px solid rgba(220,193,180,0.3);
          color: #e5e2e3;
          padding: 10px 0;
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px;
          outline: none;
          transition: border-color 0.2s;
        }
        .login-field:focus {
          border-bottom-color: #ffb68c;
        }
        .login-field::placeholder {
          color: rgba(220,193,180,0.25);
        }
      `}</style>

      <main style={{ position: 'relative', zIndex: 10, display: 'flex', height: '100vh', width: '100%' }}>

        {/* Left — branding + telemetry */}
        <section style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '48px 64px', animation: 'fadeInUp 0.8s ease both' }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 36, height: 36, border: '2px solid #da7635', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span className="material-symbols-outlined" style={{ color: '#da7635', fontSize: 20 }}>shield</span>
            </div>
            <span style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 16, letterSpacing: '0.25em', textTransform: 'uppercase', color: '#e5e2e3' }}>AeroGuard</span>
          </div>

          {/* Hero text */}
          <div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 9, letterSpacing: '0.3em', color: 'rgba(220,193,180,0.5)', textTransform: 'uppercase', marginBottom: 16 }}>
              AI Surveillance Command
            </div>
            <h1 style={{ fontFamily: 'Space Grotesk', fontWeight: 300, fontSize: 56, lineHeight: 1.1, color: '#fff', margin: 0, letterSpacing: '-0.01em' }}>
              AI-Powered<br />
              <span style={{ color: '#da7635' }}>Urban Safety</span>
            </h1>
            <p style={{ fontFamily: 'Space Grotesk', fontSize: 11, letterSpacing: '0.3em', color: 'rgba(220,193,180,0.5)', textTransform: 'uppercase', marginTop: 20 }}>
              Detect → Analyze → Respond → Resolve
            </p>
          </div>

          {/* Telemetry widgets */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {[
              { label: 'Live Monitoring', value: '42', unit: 'NODES', icon: 'sensors', color: '#4caf50', pulse: true },
              { label: 'Incident Detected', value: 'SEC-7', unit: 'ALPHA', icon: 'location_searching', color: '#ffb68c', pulse: false },
              { label: 'Drone Dispatched', value: 'UAV-09', unit: 'EN ROUTE', icon: 'flight_takeoff', color: 'rgba(220,193,180,0.6)', pulse: false },
            ].map(w => (
              <div key={w.label} style={{
                background: 'rgba(16,20,25,0.5)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(143,145,149,0.1)',
                padding: '20px 20px',
                borderLeft: `2px solid ${w.color}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <span style={{ fontFamily: 'Space Grotesk', fontSize: 8, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(220,193,180,0.5)' }}>{w.label}</span>
                  {w.pulse && <div style={{ width: 6, height: 6, borderRadius: '50%', background: w.color, animation: 'pulse-dot 2s infinite' }} />}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="material-symbols-outlined" style={{ color: w.color, fontSize: 20 }}>{w.icon}</span>
                  <span style={{ fontFamily: 'Space Grotesk', fontSize: 20, fontWeight: 700, color: w.color }}>
                    {w.value} <span style={{ fontSize: 10, fontWeight: 300, color: 'rgba(220,193,180,0.5)' }}>{w.unit}</span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Right — login panel */}
        <section style={{
          width: 420, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: '48px 56px', position: 'relative',
          animation: 'fadeInUp 0.8s ease 0.15s both',
        }}>
          {/* Watermark */}
          <div style={{ position: 'absolute', top: 0, right: 0, fontSize: 160, fontFamily: 'Space Grotesk', fontWeight: 700, color: 'rgba(255,255,255,0.03)', lineHeight: 1, userSelect: 'none', pointerEvents: 'none' }}>AG</div>

          <div style={{ width: '100%', maxWidth: 320, position: 'relative', zIndex: 1 }}>
            {/* Brand */}
            <div style={{ marginBottom: 48 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
                <div style={{ width: 28, height: 28, background: '#da7635', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span className="material-symbols-outlined" style={{ color: '#fff', fontSize: 16 }}>security</span>
                </div>
                <span style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 18, letterSpacing: '0.05em', color: '#e5e2e3' }}>AeroGuard</span>
              </div>
              <h2 style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 28, color: '#fff', margin: '0 0 6px' }}>Welcome Back</h2>
              <p style={{ fontFamily: 'Space Grotesk', fontSize: 9, letterSpacing: '0.25em', textTransform: 'uppercase', color: 'rgba(220,193,180,0.5)', margin: 0 }}>Command Center Access</p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
              <div>
                <label style={{ fontFamily: 'Space Grotesk', fontSize: 9, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(220,193,180,0.7)', display: 'block', marginBottom: 8 }}>
                  Operator Identity
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    className="login-field"
                    type="text"
                    placeholder="username"
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    autoComplete="off"
                  />
                  <span className="material-symbols-outlined" style={{ position: 'absolute', right: 0, top: 10, fontSize: 18, color: 'rgba(220,193,180,0.4)' }}>badge</span>
                </div>
              </div>

              <div>
                <label style={{ fontFamily: 'Space Grotesk', fontSize: 9, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(220,193,180,0.7)', display: 'block', marginBottom: 8 }}>
                  Security Protocol
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    className="login-field"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                  />
                  <span className="material-symbols-outlined" style={{ position: 'absolute', right: 0, top: 10, fontSize: 18, color: 'rgba(220,193,180,0.4)' }}>lock</span>
                </div>
              </div>

              {error && (
                <div style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#ff4444', letterSpacing: '0.1em', padding: '8px 12px', background: 'rgba(255,68,68,0.08)', border: '1px solid rgba(255,68,68,0.2)' }}>
                  {error}
                </div>
              )}

              <button
                type="submit"
                style={{
                  width: '100%', background: '#da7635', color: '#1a0a00',
                  padding: '16px', fontFamily: 'Space Grotesk', fontWeight: 700,
                  fontSize: 12, letterSpacing: '0.2em', textTransform: 'uppercase',
                  border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', gap: 10, transition: 'background 0.2s',
                  marginTop: 8,
                }}
                onMouseEnter={e => (e.currentTarget.style.background = '#c06828')}
                onMouseLeave={e => (e.currentTarget.style.background = '#da7635')}
              >
                <span>Initialize Access</span>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_forward</span>
              </button>
            </form>

            {/* Footer */}
            <div style={{ marginTop: 48 }}>
              <div style={{ width: 40, height: 1, background: 'rgba(220,193,180,0.15)', marginBottom: 12 }} />
              <p style={{ fontFamily: 'Space Grotesk', fontSize: 8, letterSpacing: '0.15em', textTransform: 'uppercase', color: 'rgba(220,193,180,0.3)', lineHeight: 1.8, maxWidth: 200 }}>
                Authorized personnel only. All access attempts are logged and monitored.
              </p>
            </div>
          </div>

          {/* Bottom status bar */}
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0,
            padding: '12px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            background: 'rgba(0,0,0,0.3)', backdropFilter: 'blur(8px)',
            borderTop: '1px solid rgba(85,67,57,0.15)',
          }}>
            <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#4caf50', animation: 'pulse-dot 2s infinite' }} />
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: 8, color: '#4caf50', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Secure</span>
              </div>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 8, color: 'rgba(220,193,180,0.35)', letterSpacing: '0.1em' }}>{ts}</span>
              <span style={{ fontFamily: 'JetBrains Mono', fontSize: 8, color: 'rgba(220,193,180,0.35)', letterSpacing: '0.1em' }}>{ds}</span>
            </div>
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: 8, color: 'rgba(220,193,180,0.25)', letterSpacing: '0.1em' }}>v4.8.2-tactical</span>
          </div>
        </section>
      </main>
    </div>
  )
}
