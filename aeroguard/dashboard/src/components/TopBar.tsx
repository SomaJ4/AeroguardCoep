interface TopBarProps {
  title: string
  subtitle?: string
}

export default function TopBar({ title, subtitle }: TopBarProps) {
  const now = new Date().toLocaleTimeString('en-US', { hour12: false })

  return (
    <header style={{
      position: 'fixed', top: 0, left: 80, right: 0, height: 56,
      background: 'rgba(19,19,20,0.95)', backdropFilter: 'blur(12px)',
      borderBottom: '1px solid rgba(85,67,57,0.3)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 24px', zIndex: 40
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{ color: '#ffb68c', fontSize: 18, fontFamily: 'Space Grotesk', fontWeight: 300, letterSpacing: '0.2em' }}>
          {title}
        </span>
        {subtitle && (
          <span style={{ color: 'rgba(220,193,180,0.5)', fontSize: 10, fontFamily: 'JetBrains Mono', letterSpacing: '0.1em' }}>
            {subtitle}
          </span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 6, height: 6, background: '#ffb68c', borderRadius: '50%' }} className="animate-pulse" />
          <span style={{ fontSize: 9, fontFamily: 'JetBrains Mono', color: '#ffb68c' }}>SYSTEM ACTIVE</span>
        </div>
        <span style={{ fontSize: 9, fontFamily: 'JetBrains Mono', color: 'rgba(163,140,128,0.6)' }}>{now}</span>
        <span className="material-symbols-outlined" style={{ color: 'rgba(255,182,140,0.6)', cursor: 'pointer' }}>notifications</span>
        <span className="material-symbols-outlined" style={{ color: 'rgba(255,182,140,0.6)', cursor: 'pointer' }}>settings</span>
      </div>
    </header>
  )
}
