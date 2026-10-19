import { useState } from 'react'
import { LANG, ORDER } from '../lang.js'
import { tok } from '../highlight.js'

const FILTERS = [['all', 'All'], ['loops', 'Loops'], ['recursion', 'Recursion'], ['math', 'Math'], ['arrays', 'Arrays'], ['strings', 'Strings'], ['library', 'Library']]
const TILE = ['#6CB6FF', '#FFA657', '#C792EA', '#7EE787', '#FFCB6B', '#89DDFF', '#FF8F85']

export default function SamplesPage({ catalog, open, offline }) {
  const [filter, setFilter] = useState('all')
  const shown = catalog.filter(s => filter === 'all' || s.topics.includes(filter))
  return (
    <>
      <section style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap', padding: '40px 0 24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 640 }}>
          <span className="mono" style={{ fontSize: 12, letterSpacing: '0.14em', color: '#FFA657' }}>SAMPLES</span>
          <h1 style={{ margin: 0, fontSize: 'clamp(30px, 3.6vw, 44px)', fontWeight: 650, letterSpacing: '-0.025em' }}>Programs ready to <span style={{ color: '#FFA657' }}>shift</span>.</h1>
        </div>
      </section>
      <div role="group" aria-label="Filter by topic" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 22 }}>
        {FILTERS.map(([id, label]) => {
          const on = id === filter
          const n = id === 'all' ? catalog.length : catalog.filter(s => s.topics.includes(id)).length
          return (
            <button key={id} type="button" className="sp-chip" aria-pressed={on} onClick={() => setFilter(id)}
              style={{ minHeight: 40, padding: '0 14px', borderRadius: 999, border: `1px solid ${on ? '#FFA657' : '#2A303A'}`, background: on ? 'rgba(255,166,87,0.12)' : '#11141A', color: on ? '#FFA657' : '#C5CBD5', fontSize: 13.5, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              {label}<span className="mono" style={{ fontSize: 11, opacity: 0.75 }}>{n}</span>
            </button>
          )
        })}
        <span style={{ marginLeft: 'auto', fontSize: 13, color: '#7B8394' }}>{shown.length} of {catalog.length} samples</span>
      </div>
      {!catalog.length && (
        <div role="status" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 18, borderRadius: 16, background: '#11141A', border: '1px solid #1F242D', color: '#A3ABB9' }}>
          <span className="cs-pulse" style={{ width: 8, height: 8, borderRadius: '50%', background: offline ? '#FF8F85' : '#FFA657', flex: 'none' }} />
          {offline ? 'The API is offline, so there are no samples to show yet. Start the backend (start.bat) and this page fills in by itself.' : 'Loading the samples from the API…'}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 380px), 1fr))', gap: 16 }}>
        {shown.map((s, i) => {
          const col = TILE[catalog.indexOf(s) % TILE.length]
          return (
            <article key={s.id} className="sp-card sp-in" style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 18, borderRadius: 16, background: '#11141A', border: '1px solid #1F242D', animationDelay: `${Math.min(i * 40, 320)}ms` }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                  <span className="mono" style={{ flex: 'none', width: 42, height: 42, borderRadius: 11, display: 'flex', alignItems: 'center', justifyContent: 'center', background: col + '1F', color: col, fontSize: 13, fontWeight: 600 }}>{'{ }'}</span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                    <span style={{ fontSize: 16, fontWeight: 600 }}>{s.name}</span>
                    <span className="mono" style={{ fontSize: 12, color: '#7B8394' }}>{s.file}{ORDER.map(l => ` · .${LANG[l].ext}`).join('').replace(/^ · /, '')}</span>
                  </div>
                </div>
                <span className="mono" style={{ flex: 'none', fontSize: 11, padding: '4px 9px', borderRadius: 999, color: '#7EE787', background: 'rgba(126,231,135,0.12)' }}>Ready</span>
              </div>
              <p style={{ margin: 0, color: '#A3ABB9', lineHeight: 1.55, fontSize: 13.5 }}>{s.desc}</p>
              <div className="mono" style={{ padding: '10px 12px', borderRadius: 10, background: '#0B0D12', border: '1px solid #1B1F27', fontSize: 12.5, lineHeight: '20px', overflow: 'hidden' }}>
                {s.code.python.split('\n').slice(0, 3).map((l, j) => (
                  <div key={j} style={{ whiteSpace: 'pre' }}>{tok(l).map((t, k) => <span key={k} style={{ color: t.c }}>{t.t}</span>)}</div>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', marginTop: 'auto' }}>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {s.topics.map(t => <span key={t} style={{ fontSize: 12, padding: '3px 9px', borderRadius: 6, background: '#1A1E26', color: '#C5CBD5' }}>{t}</span>)}
                </div>
                <button type="button" className="cs-btn" onClick={() => open(s.id)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 40, padding: '0 12px', borderRadius: 9, background: '#FFA657', color: '#1A1006', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
                  Open in playground
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14" /><path d="M13 6l6 6-6 6" /></svg>
                </button>
              </div>
            </article>
          )
        })}
      </div>
      {!shown.length && <div style={{ padding: 40, textAlign: 'center', border: '1px dashed #2A303A', borderRadius: 16, color: '#7B8394' }}>No samples in this category.</div>}
    </>
  )
}
