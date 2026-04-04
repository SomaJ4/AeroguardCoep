interface SidebarProps {
  active: 'command' | 'tactical' | 'intel'
  onNav: (page: 'command' | 'tactical' | 'intel') => void
}

export default function Sidebar({ active, onNav }: SidebarProps) {
  const items = [
    { id: 'command' as const, icon: 'terminal', label: 'Command' },
    { id: 'tactical' as const, icon: 'map', label: 'Tactical' },
    { id: 'intel' as const, icon: 'emergency_home', label: 'Intel' },
  ]

  return (
    <aside style={{
      position: 'fixed', left: 0, top: 0, height: '100vh', width: 80,
      background: '#0e0e0f', borderRight: '1px solid rgba(85,67,57,0.3)',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '24px 0', zIndex: 50
    }}>
      <div style={{ marginBottom: 32, textAlign: 'center' }}>
        <div style={{ color: '#ffb68c', fontSize: 10, letterSpacing: '0.2em', fontFamily: 'Space Grotesk' }}>AERO</div>
        <div style={{ color: '#ffb68c', fontSize: 10, letterSpacing: '0.2em', fontFamily: 'Space Grotesk' }}>GUARD</div>
      </div>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
        {items.map(item => (
          <button key={item.id} onClick={() => onNav(item.id)} style={{
            width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '12px 0', cursor: 'pointer', border: 'none',
            borderLeft: active === item.id ? '2px solid #ffb68c' : '2px solid transparent',
            background: active === item.id ? 'rgba(218,118,53,0.1)' : 'transparent',
            color: active === item.id ? '#ffb68c' : 'rgba(220,193,180,0.5)',
            transition: 'all 0.2s',
          }}>
            <span className="material-symbols-outlined">{item.icon}</span>
            <span style={{ fontSize: 8, letterSpacing: '0.1em', fontFamily: 'Space Grotesk', marginTop: 4, textTransform: 'uppercase' }}>{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  )
}
