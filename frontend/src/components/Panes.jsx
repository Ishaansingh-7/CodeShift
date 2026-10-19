import { Suspense, lazy, useMemo } from 'react'
import { LANG, LC, ORDER } from '../lang.js'
import { tok } from '../highlight.js'

const SourceEditor = lazy(() => import('./SourceEditor.jsx'))

const PILL = { display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 36, padding: '0 12px', borderRadius: 8, fontSize: 13, fontFamily: 'inherit', cursor: 'pointer' }
const SKEL = [62, 38, 74, 55, 30, 68, 46, 80, 24, 58, 40, 66]
const ORANGE = { bg: 'rgba(255,166,87,0.11)', bar: '#FFA657' }
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`

function ViewSwitch({ fs, setFs }) {
  const views = [['', 'Split', '#C792EA', false], ['src', 'Source only', '#6CB6FF', true], ['tgt', 'Output only', '#FFA657', true]]
  return (
    <div role="group" aria-label="View" style={{ display: 'flex', gap: 4, padding: 4, borderRadius: 10, background: '#0B0D12', border: '1px solid #1F242D' }}>
      {views.map(([id, label, dot, full]) => (
        <button key={id} type="button" className="cs-btn" aria-pressed={fs === id} onClick={() => setFs(id)}
          style={{ minHeight: 36, padding: '0 12px', borderRadius: 7, border: 'none', background: fs === id ? '#1C212A' : 'transparent', color: fs === id ? '#FFFFFF' : '#A3ABB9', fontSize: 13, fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: dot }} />{label}
          {full && <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 9V4h5" /><path d="M20 9V4h-5" /><path d="M4 15v5h5" /><path d="M20 15v5h-5" /></svg>}
        </button>
      ))}
    </div>
  )
}

function IrBridge({ flowing }) {
  return (
    <div className="cs-bridge" aria-hidden="true" style={{ flex: '0 0 40px', alignSelf: 'stretch', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
      <div style={{ position: 'relative', width: 40, height: 180 }}>
        {[10, 30, 50, 70, 90].map((p, i) => (
          <span key={i} className="cs-pkt" style={{ top: `${p}%`, background: flowing ? '#FFA657' : '#3E5F80', boxShadow: `0 0 8px ${flowing ? '#FFA657' : '#3E5F80'}`, animationDuration: flowing ? '0.7s' : '2.6s', animationDelay: `${(i * (flowing ? 0.13 : 0.45)).toFixed(2)}s` }} />
        ))}
      </div>
      <span className="mono" style={{ fontSize: 10, letterSpacing: '0.12em', color: flowing ? '#FFA657' : '#5E6674' }}>IR</span>
    </div>
  )
}

const Icon = ({ label, onClick, children }) => (
  <button type="button" className="cs-btn" aria-label={label} title={label} onClick={onClick}
    style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'transparent', border: 'none', borderRadius: 8, color: '#A3ABB9', cursor: 'pointer' }}>{children}</button>
)

function Line({ n, toks, group, hg, setHg, hl, cursor }) {
  const on = group !== null && group === hg
  return (
    <div className="cs-in" onMouseEnter={() => setHg(group ?? -1)}
      style={{ display: 'flex', minHeight: 22, paddingRight: 16, cursor: 'default', transition: 'background .15s ease', background: on ? hl.bg : 'transparent', boxShadow: `inset 3px 0 0 ${on ? hl.bar : 'transparent'}` }}>
      <span style={{ width: 52, flex: 'none', textAlign: 'right', paddingRight: 18, boxSizing: 'border-box', userSelect: 'none', color: on ? hl.bar : '#4A5260' }}>{n}</span>
      <span style={{ whiteSpace: 'pre' }}>
        {toks.map((t, i) => <span key={i} style={{ color: t.c }}>{t.t}</span>)}
        {cursor && <span className="cs-caret" />}
      </span>
    </div>
  )
}

function Blocked({ tgt, error, works, pickTgt }) {
  return (
    <div className="cs-up" style={{ margin: '14px 20px', padding: '18px 20px', borderRadius: 14, background: 'rgba(255,203,107,0.05)', border: '1px solid rgba(255,203,107,0.28)', fontFamily: "'Geist', system-ui, sans-serif" }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 15, fontWeight: 600, color: '#E6E9EF' }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FFCB6B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 8v5" /><path d="M12 16.5v.01" /></svg>
        This program can't be translated to {LANG[tgt].short} yet.
      </div>
      <div className="mono" style={{ marginTop: 8, fontSize: 12, lineHeight: 1.6, color: '#7B8394' }}>{error.message}</div>
      <div style={{ marginTop: 16, fontSize: 13, color: '#C5CBD5' }}>{works.length ? 'Try another language:' : 'No other target can translate it yet either.'}</div>
      {works.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
          {works.map(l => (
            <button key={l} type="button" className="cs-btn" onClick={() => pickTgt(l)}
              style={{ ...PILL, background: '#151920', color: '#E6E9EF', border: '1px solid #2A303A' }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: LC[l] }} />{LANG[l].short}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Panes({ ctx, onType, pickSample, pickCustom, pickTgt }) {
  const { cfg, catalog, code, shown, stale, error, blocked, empty, busy, rev, hg, setHg, fs, setFs, srcFile, tgtFile, result } = ctx
  const srcError = blocked ? null : error
  const codeH = fs ? 'max(440px, 72vh)' : '440px'
  const srcLines = result && !error ? result.srcLines : []
  const highlight = useMemo(() => srcLines.flatMap((l, i) => l.group !== null && l.group === hg ? [i + 1] : []), [srcLines, hg])
  const out = useMemo(() => {
    let idx = 0
    const rows = []
    ;(shown?.tgtLines || []).forEach((row, li) => {
      const toks = tok(row.text)
      const start = idx
      idx += toks.length
      if (rev >= 0 && start > rev) return
      rows.push({ n: li + 1, group: row.group, toks: rev >= 0 ? toks.slice(0, Math.max(0, rev - start)) : toks, cursor: rev >= 0 && rev >= start && rev < idx })
    })
    return rows
  }, [shown, rev])
  const flowing = busy || rev >= 0
  const srcCount = code ? code.replace(/\n$/, '').split('\n').length : 0
  const idle = !!error || empty || !shown
  const copy = () => !idle && navigator.clipboard?.writeText(shown.output)
  const download = () => {
    if (idle) return
    const url = URL.createObjectURL(new Blob([shown.output], { type: 'text/plain' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: cfg.tgt === 'java' ? 'Main.java' : tgtFile })
    a.click()
    URL.revokeObjectURL(url)
  }
  const pane = (border, display) => ({ display, flex: '1 1 0', minWidth: 0, background: '#11141A', border: `1px solid ${border}`, borderRadius: 16, overflow: 'hidden', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03), 0 24px 60px rgba(0,0,0,0.35)' })
  const head = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '12px 16px', borderBottom: '1px solid #1F242D' }
  return (
    <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', padding: '8px 8px 8px 14px', background: 'rgba(14,17,22,0.9)', border: '1px solid #1B1F27', borderRadius: 12 }}>
        <div className="mono" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', fontSize: 12.5 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: '#6CB6FF' }} /><span>{srcFile}</span><span style={{ color: '#7B8394' }}>{plural(srcCount, 'line')}</span></span>
          <span style={{ color: '#C792EA' }}>⇄</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: '#FFA657' }} /><span>{tgtFile}</span><span style={{ color: '#7B8394' }}>{blocked ? 'not supported' : plural(empty ? 0 : shown?.tgtLines.length ?? 0, 'line')}</span></span>
        </div>
        <ViewSwitch fs={fs} setFs={setFs} />
      </div>
      <div className="cs-panes" style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
        <section className="cs-pane" aria-label="Source" style={pane(hg >= 0 ? 'rgba(108,182,255,0.45)' : srcError ? 'rgba(255,143,133,0.45)' : '#1F242D', fs === 'tgt' ? 'none' : 'block')}>
          <div style={head}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 10, height: 10, borderRadius: 3, background: '#6CB6FF' }} />
              <span className="mono" style={{ fontSize: 13, fontWeight: 500 }}>{srcFile}</span>
              <span style={{ fontSize: 11, color: '#6CB6FF', background: 'rgba(108,182,255,0.12)', padding: '3px 8px', borderRadius: 6, letterSpacing: '0.06em' }}>SOURCE</span>
            </div>
            <span style={{ fontSize: 12, color: '#7B8394' }}>{plural(srcCount, 'line')} · {plural(result?.stats.tokens ?? 0, 'token')}</span>
          </div>
          <div className="cs-chips" style={{ display: 'flex', gap: 6, flexWrap: 'nowrap', overflowX: 'auto', alignItems: 'center', padding: '10px 16px', borderBottom: '1px solid #1B1F27' }}>
            <span style={{ flex: 'none', fontSize: 11, color: '#7B8394', letterSpacing: '0.08em', marginRight: 4 }}>CODE</span>
            <button type="button" className="cs-btn mono" aria-pressed={cfg.sample === null} onClick={pickCustom}
              style={{ ...PILL, flex: 'none', whiteSpace: 'nowrap', minHeight: 32, padding: '0 10px', fontSize: 12, background: cfg.sample === null ? 'rgba(108,182,255,0.14)' : 'transparent', color: cfg.sample === null ? '#6CB6FF' : '#A3ABB9', border: `1px solid ${cfg.sample === null ? 'rgba(108,182,255,0.4)' : '#2A303A'}` }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4z" /><path d="M13.5 6.5l4 4" /></svg>
              Your code
            </button>
            <span aria-hidden="true" style={{ flex: 'none', width: 1, height: 18, margin: '0 8px', background: '#2A303A' }} />
            <span style={{ flex: 'none', fontSize: 11, color: '#7B8394', letterSpacing: '0.08em', marginRight: 4 }}>SAMPLE</span>
            {catalog.map(s => {
              const on = s.id === cfg.sample
              return (
                <button key={s.id} type="button" className="cs-btn mono" aria-pressed={on} onClick={() => pickSample(s.id)}
                  style={{ ...PILL, flex: 'none', whiteSpace: 'nowrap', minHeight: 32, padding: '0 10px', fontSize: 12, background: on ? 'rgba(108,182,255,0.14)' : 'transparent', color: on ? '#6CB6FF' : '#A3ABB9', border: `1px solid ${on ? 'rgba(108,182,255,0.4)' : '#2A303A'}` }}>
                  {s.file}
                </button>
              )
            })}
          </div>
          <div style={{ padding: 0 }}>
            <Suspense fallback={<div className="cs-pulse" style={{ height: codeH, background: '#11141A' }} />}>
            <SourceEditor value={code} language={LANG[cfg.src].monaco} height={codeH} onChange={onType}
              onHoverLine={n => setHg(n && srcLines[n - 1]?.group != null ? srcLines[n - 1].group : -1)} highlight={highlight} error={srcError} />
            </Suspense>
          </div>
        </section>
        {!fs && <IrBridge flowing={flowing} />}
        <section className="cs-pane" aria-label="Output" style={pane(hg >= 0 ? 'rgba(255,166,87,0.45)' : '#1F242D', fs === 'src' ? 'none' : 'block')}>
          <div style={head}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 10, height: 10, borderRadius: 3, background: '#FFA657' }} />
              <span className="mono" style={{ fontSize: 13, fontWeight: 500 }}>{tgtFile}</span>
              {blocked ? <span style={{ fontSize: 11, color: '#FFCB6B', background: 'rgba(255,203,107,0.12)', padding: '3px 8px', borderRadius: 6, letterSpacing: '0.06em' }}>NOT SUPPORTED</span>
                : <span style={{ fontSize: 11, color: stale ? '#FF8F85' : '#FFA657', background: stale ? 'rgba(255,143,133,0.12)' : 'rgba(255,166,87,0.12)', padding: '3px 8px', borderRadius: 6, letterSpacing: '0.06em' }}>{stale ? 'STALE · FIX THE ERROR' : 'OUTPUT'}</span>}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, opacity: idle ? 0.4 : 1 }}>
              <Icon label="Copy output" onClick={copy}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></svg></Icon>
              <Icon label="Download output" onClick={download}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3v12" /><path d="M7 10l5 5 5-5" /><path d="M4 21h16" /></svg></Icon>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', padding: '10px 16px', borderBottom: '1px solid #1B1F27' }}>
            <span style={{ fontSize: 11, color: '#7B8394', letterSpacing: '0.08em', marginRight: 4 }}>TARGET</span>
            {ORDER.filter(l => l !== cfg.src).map(l => {
              const on = l === cfg.tgt
              return (
                <button key={l} type="button" className="cs-btn" aria-pressed={on} onClick={() => pickTgt(l)}
                  style={{ ...PILL, ...(on ? { background: '#FFA657', color: '#1A1006', border: '1px solid #FFA657', fontWeight: 600 } : { background: 'transparent', color: '#C5CBD5', border: '1px solid #2A303A' }) }}>
                  {LANG[l].short}
                </button>
              )
            })}
          </div>
          <div className={'cs-code mono' + (stale && !blocked && !empty ? ' cs-stale' : '')} onMouseLeave={() => setHg(-1)}
            style={{ height: codeH, overflow: 'auto', padding: '12px 0', fontSize: 13, lineHeight: '22px' }}>
            {empty ? (
              <div style={{ padding: '6px 20px', color: '#7B8394', fontFamily: "'Geist', system-ui, sans-serif", lineHeight: 1.6 }}>
                Write or paste a {LANG[cfg.src].short} program in the editor. It shifts to {LANG[cfg.tgt].short} as you type.
              </div>
            ) : blocked && !busy ? <Blocked tgt={cfg.tgt} error={error} works={result.works || []} pickTgt={pickTgt} />
            : busy || (!shown && !error) ? (
              <div aria-label="Waiting for the compiler" style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '6px 20px 6px 52px' }}>
                {SKEL.map((w, i) => <div key={i} className="cs-pulse" style={{ height: 12, borderRadius: 6, background: '#1E232C', width: `${w}%`, animationDelay: `${i * 70}ms` }} />)}
              </div>
            ) : shown ? out.map(r => <Line key={r.n} {...r} hg={stale ? -2 : hg} setHg={stale ? () => {} : setHg} hl={ORANGE} />)
              : error ? <div style={{ padding: '6px 20px', color: '#7B8394', fontFamily: "'Geist', system-ui, sans-serif" }}>No output yet. {error.message}</div> : null}
          </div>
        </section>
      </div>
    </div>
  )
}

