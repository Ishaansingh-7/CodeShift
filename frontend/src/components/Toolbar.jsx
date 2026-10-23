export default function Toolbar({ optimize, toggleOpt, rt, toggleRt, busy, doShift }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
      <button type="button" className="cs-btn" aria-pressed={optimize} onClick={toggleOpt}
        style={{ display: 'flex', alignItems: 'center', gap: 10, minHeight: 44, padding: '0 14px', background: 'transparent', border: '1px solid var(--c2A303A)', borderRadius: 10, color: 'var(--cC5CBD5)', fontSize: 14, cursor: 'pointer' }}>
        <span style={{ position: 'relative', width: 30, height: 18, borderRadius: 999, flex: 'none', transition: 'background .2s ease', background: optimize ? 'var(--c7EE787)' : 'var(--c2A303A)' }}>
          <span style={{ position: 'absolute', top: 2, left: optimize ? 14 : 2, width: 14, height: 14, borderRadius: '50%', transition: 'left .2s ease', background: optimize ? 'var(--c0C2A10)' : 'var(--cA3ABB9)' }} />
        </span>
        Optimize IR
      </button>
      <button type="button" className="cs-btn" aria-pressed={rt} onClick={toggleRt}
        style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 44, padding: '0 16px', background: rt ? 'color-mix(in srgb, var(--cC792EA) 10%, transparent)' : 'transparent', border: `1px solid ${rt ? 'color-mix(in srgb, var(--cC792EA) 45%, transparent)' : 'var(--c2A303A)'}`, borderRadius: 10, color: 'var(--cC5CBD5)', fontSize: 14, cursor: 'pointer' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16" /><path d="M3 21v-5h5" /></svg>
        Round-trip
      </button>
      <button type="button" className="cs-shift" onClick={doShift}
        style={{ display: 'flex', alignItems: 'center', gap: 10, minHeight: 44, padding: '0 20px', background: 'var(--cFFA657)', border: 'none', borderRadius: 10, color: 'var(--c1A1006)', fontSize: 15, fontWeight: 650, cursor: 'pointer', boxShadow: '0 8px 24px color-mix(in srgb, var(--cFFA657) 25%, transparent)' }}>
        {busy ? 'Shifting…' : 'Shift'}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14" /><path d="M13 6l6 6-6 6" /></svg>
      </button>
    </div>
  )
}
