const NAV = [['play', 'Playground'], ['samples', 'Samples'], ['pipe', 'Pipeline']]

export default function Header({ view, setView }) {
  return (
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', padding: '18px 0', borderBottom: '1px solid #1B1F27' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden="true">
          <rect x="0.5" y="0.5" width="33" height="33" rx="9" fill="#12151B" stroke="#2A303A" />
          <path d="M14 11 L8 17 L14 23" stroke="#6CB6FF" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M20 11 L26 17 L20 23" stroke="#FFA657" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M18.5 9.5 L15.5 24.5" stroke="#5B6472" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <span style={{ fontWeight: 650, fontSize: 20, letterSpacing: '-0.02em' }}>Code<span style={{ color: '#FFA657' }}>Shift</span></span>
        <span className="mono" style={{ fontSize: 11, color: '#A3ABB9', border: '1px solid #2A303A', borderRadius: 999, padding: '3px 8px' }}>compiler · v2</span>
      </div>
      <nav aria-label="Main" style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
        {NAV.map(([id, label]) => (
          <button key={id} type="button" className="cs-navb" aria-current={view === id ? 'page' : 'false'} onClick={() => setView(id)}
            style={{ minHeight: 40, padding: '0 14px', borderRadius: 8, border: 'none', background: view === id ? '#181C23' : 'transparent', color: view === id ? '#FFFFFF' : '#A3ABB9', fontSize: 14, cursor: 'pointer' }}>
            {label}
          </button>
        ))}
        <a href="https://github.com/Ishaansingh-7/CodeShift" target="_blank" rel="noreferrer" style={{ padding: '10px 14px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M16 18l6-6-6-6" /><path d="M8 6l-6 6 6 6" /></svg>
          Source
        </a>
      </nav>
    </header>
  )
}
