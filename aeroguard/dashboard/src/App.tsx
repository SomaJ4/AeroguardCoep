import { useState } from 'react'
import './index.css'
import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import CommandOverview from './pages/CommandOverview'
import TacticalMap from './pages/TacticalMap'
import IntelligenceHub from './pages/IntelligenceHub'

type Page = 'command' | 'tactical' | 'intel'

const PAGE_TITLES: Record<Page, { title: string; subtitle: string }> = {
  command: { title: 'OPERATIONS', subtitle: 'CITY-WIDE INCIDENT COMMAND' },
  tactical: { title: 'TACTICAL MAP', subtitle: 'DRONE DISPATCH CONTROL' },
  intel: { title: 'INTELLIGENCE HUB', subtitle: 'SIGNAL ANALYSIS & INCIDENT FEED' },
}

export default function App() {
  const [page, setPage] = useState<Page>('command')
  const { title, subtitle } = PAGE_TITLES[page]

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#131314' }}>
      <Sidebar active={page} onNav={setPage} />
      <div style={{ flex: 1, marginLeft: 80, display: 'flex', flexDirection: 'column' }}>
        <TopBar title={title} subtitle={subtitle} />
        <main style={{ flex: 1, marginTop: 56, overflow: 'hidden' }}>
          {page === 'command' && <CommandOverview />}
          {page === 'tactical' && <TacticalMap />}
          {page === 'intel' && <IntelligenceHub />}
        </main>
        {/* Status footer */}
        <footer style={{
          height: 32, background: '#0e0e0f', borderTop: '1px solid rgba(218,118,53,0.2)',
          display: 'flex', alignItems: 'center', padding: '0 16px', gap: 16, overflow: 'hidden'
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: '#ffb68c' }}>terminal</span>
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: 10, color: '#ffb68c', textTransform: 'uppercase', letterSpacing: '0.1em', whiteSpace: 'nowrap' }}>Command Log:</span>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <div className="animate-marquee" style={{ display: 'flex', gap: 48, whiteSpace: 'nowrap' }}>
              {['SYSTEM NOMINAL', 'AI CORE ONLINE', 'LIVE FEEDS SYNCED', 'DRONE FLEET READY', 'INCIDENT MONITORING ACTIVE'].map(m => (
                <span key={m} style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: 'rgba(220,193,180,0.4)', textTransform: 'uppercase' }}>{m}</span>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, background: '#ffb68c', borderRadius: '50%' }} className="animate-pulse" />
            <span style={{ fontFamily: 'JetBrains Mono', fontSize: 9, color: '#ffb68c' }}>STATUS: NOMINAL</span>
          </div>
        </footer>
      </div>
    </div>
  )
}
