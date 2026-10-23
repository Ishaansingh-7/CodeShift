import { setTheme, useTheme } from '../theme.js'

const SUN = <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
const MOON = <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>

const NAV = [['play', 'Playground'], ['samples', 'Samples'], ['pipe', 'Pipeline']]

export default function Header({ view, setView }) {
  const theme = useTheme()
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', padding: '18px 0', borderBottom: '1px solid var(--c1B1F27)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden="true">
          <rect x="0.5" y="0.5" width="33" height="33" rx="9" fill="var(--c12151B)" stroke="var(--c2A303A)" />
          <path d="M14 11 L8 17 L14 23" stroke="var(--c6CB6FF)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M20 11 L26 17 L20 23" stroke="var(--cFFA657)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M18.5 9.5 L15.5 24.5" stroke="var(--c5B6472)" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <span style={{ fontWeight: 650, fontSize: 20, letterSpacing: '-0.02em' }}>Code<span style={{ color: 'var(--cFFA657)' }}>Shift</span></span>
        <span className="mono" style={{ fontSize: 11, color: 'var(--cA3ABB9)', border: '1px solid var(--c2A303A)', borderRadius: 999, padding: '3px 8px' }}>compiler · v2</span>
      </div>
      <nav aria-label="Main" style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
        {NAV.map(([id, label]) => (
          <button key={id} type="button" className="cs-navb" aria-current={view === id ? 'page' : 'false'} onClick={() => setView(id)}
            style={{ minHeight: 40, padding: '0 14px', borderRadius: 8, border: 'none', background: view === id ? 'var(--c181C23)' : 'transparent', color: view === id ? 'var(--cFFFFFF)' : 'var(--cA3ABB9)', fontSize: 14, cursor: 'pointer' }}>
            {label}
          </button>
        ))}
        <a href="https://github.com/Ishaansingh-7/CodeShift" target="_blank" rel="noreferrer" style={{ padding: '10px 14px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M16 18l6-6-6-6" /><path d="M8 6l-6 6 6 6" /></svg>
          Source
        </a>
        <button type="button" className="cs-navb" onClick={() => setTheme(next)} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}
          style={{ width: 40, height: 40, marginLeft: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 8, border: '1px solid var(--c2A303A)', background: 'transparent', color: 'var(--cA3ABB9)', cursor: 'pointer' }}>
          {theme === 'dark' ? SUN : MOON}
        </button>
      </nav>
    </header>
  )
}
