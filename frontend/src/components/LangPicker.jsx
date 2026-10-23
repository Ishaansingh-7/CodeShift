import { useEffect, useRef, useState } from 'react'
import { LANG, ORDER } from '../lang.js'

const Check = ({ color }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10" /></svg>
)

function Picker({ title, value, color, glow, pick, open, setOpen, highlight }) {
  return (
    <div style={{ position: 'relative' }}>
      <button type="button" className="cs-btn" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: 12, minHeight: 52, minWidth: 180, padding: '0 14px', background: 'var(--c12151B)', border: `1px solid ${open ? color : 'var(--c2A303A)'}`, borderRadius: 12, color: 'var(--cE6E9EF)', fontSize: 14, cursor: 'pointer' }}>
        <span style={{ width: 10, height: 10, borderRadius: '50%', background: color, boxShadow: `0 0 10px ${glow}` }} />
        <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 2, flex: 1 }}>
          <span style={{ fontSize: 10.5, letterSpacing: '0.1em', color: 'var(--c7B8394)' }}>{title}</span>
          <span style={{ fontWeight: 600 }}>{LANG[value].label}</span>
        </span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--c7B8394)" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      {open && (
        <div role="listbox" aria-label={title === 'FROM' ? 'Source language' : 'Target language'} className="cs-up"
          style={{ position: 'absolute', top: 'calc(100% + 8px)', left: 0, zIndex: 30, width: 260, padding: 6, background: 'var(--c151920)', border: '1px solid var(--c2A303A)', borderRadius: 14, boxShadow: '0 24px 60px color-mix(in srgb, var(--c000000) 55%, transparent)' }}>
          {ORDER.map(l => (
            <button key={l} type="button" role="option" aria-selected={l === value} className="cs-menu-item" onClick={() => { setOpen(false); pick(l) }}
              style={{ width: '100%', minHeight: 44, display: 'flex', alignItems: 'center', gap: 10, padding: '0 10px', border: 'none', borderRadius: 9, background: l === value ? highlight : 'transparent', color: 'var(--cE6E9EF)', fontSize: 14, cursor: 'pointer', textAlign: 'left' }}>
              <span className="mono" style={{ fontSize: 11, width: 34, textAlign: 'center', padding: '3px 0', borderRadius: 6, background: 'var(--c1E232C)', color: 'var(--cA3ABB9)' }}>.{LANG[l].ext}</span>
              <span style={{ flex: 1, fontWeight: 500 }}>{LANG[l].label}</span>
              <span style={{ fontSize: 11, color: 'var(--c7B8394)' }}>{LANG[l].typing}</span>
              {l === value && <Check color={color} />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function LangPicker({ src, tgt, pickSrc, pickTgt, swap }) {
  const [menu, setMenu] = useState('')
  const [spin, setSpin] = useState(0)
  const ref = useRef(null)
  useEffect(() => {
    if (!menu) return
    const close = e => { if (!ref.current?.contains(e.target)) setMenu('') }
    const esc = e => { if (e.key === 'Escape') setMenu('') }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [menu])
  return (
    <div ref={ref} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
      <Picker title="FROM" value={src} color="var(--c6CB6FF)" glow="color-mix(in srgb, var(--c6CB6FF) 60%, transparent)" highlight="color-mix(in srgb, var(--c6CB6FF) 10%, transparent)" pick={pickSrc}
        open={menu === 'from'} setOpen={o => setMenu(o ? 'from' : '')} />
      <button type="button" className="cs-btn" aria-label="Swap direction" onClick={() => { setSpin(spin + 180); swap() }}
        style={{ width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--c1A1E26)', border: '1px solid var(--c2A303A)', borderRadius: '50%', color: 'var(--cE6E9EF)', cursor: 'pointer' }}>
        <svg width="18" height="18" style={{ transform: `rotate(${spin}deg)`, transition: 'transform .45s cubic-bezier(.2,.7,.2,1)' }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M7 7h13l-4-4" /><path d="M17 17H4l4 4" /></svg>
      </button>
      <Picker title="TO" value={tgt} color="var(--cFFA657)" glow="color-mix(in srgb, var(--cFFA657) 60%, transparent)" highlight="color-mix(in srgb, var(--cFFA657) 10%, transparent)" pick={pickTgt}
        open={menu === 'to'} setOpen={o => setMenu(o ? 'to' : '')} />
    </div>
  )
}
