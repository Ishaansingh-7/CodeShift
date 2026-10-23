import { LANG, LC, alpha, fileOf } from '../lang.js'

export default function HistoryList({ hist, cur, catalog, restore, clear }) {
  const cards = hist.map((e, i) => {
    const isCur = e.src === cur.src && e.tgt === cur.tgt && e.sample === cur.sample && e.code === cur.code
    const d = new Date(e.t)
    const sample = catalog.find(s => s.id === e.sample)
    const ok = e.match && (e.match === 'same output' || e.match.split('/')[0] === e.match.split('/')[1])
    return (
      <button key={`${e.t}-${i}`} type="button" className={'cs-hcard' + (i === 0 ? ' cs-hin' : '')} onClick={() => !isCur && restore(e)}
        aria-label={`Restore ${LANG[e.src].short} to ${LANG[e.tgt].short}, ${sample ? sample.file + ' sample' : 'your code'}`}
        style={{ flex: '0 0 230px', textAlign: 'left', padding: '12px 14px', borderRadius: 12, border: `1px solid ${isCur ? alpha(LC[e.tgt], 0.6) : 'var(--c232833)'}`, background: isCur ? alpha(LC[e.tgt], 0.07) : 'var(--c0E1116)', color: 'var(--cE6E9EF)', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <span className="mono" style={{ fontSize: 14, fontWeight: 600 }}>
            <span style={{ color: LC[e.src], textShadow: `0 0 6px ${alpha(LC[e.src], 0.25)}` }}>{LANG[e.src].short}</span>
            <span style={{ color: 'var(--cC792EA)' }}> → </span>
            <span style={{ color: LC[e.tgt], textShadow: `0 0 6px ${alpha(LC[e.tgt], 0.25)}` }}>{LANG[e.tgt].short}</span>
          </span>
          <span className="mono" style={{ fontSize: 11, color: isCur ? LC[e.tgt] : 'var(--c7B8394)' }}>
            {isCur ? 'now' : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`}
          </span>
        </span>
        <span className="mono" style={{ fontSize: 12, color: 'var(--cA3ABB9)' }}>{fileOf(e.src)} → {fileOf(e.tgt)}</span>
        <span style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span style={{ color: 'var(--c7B8394)' }}>{e.srcN} → {e.tgtN} lines</span>
          <span style={{ color: e.match === null ? 'var(--c7B8394)' : ok ? 'var(--c7EE787)' : 'var(--cFF8F85)' }}>{e.match === null ? 'testing…' : e.match.includes('/') ? `${e.match} match` : e.match}</span>
        </span>
      </button>
    )
  })
  return (
    <section aria-label="Recent shifts" style={{ marginTop: 14, padding: '16px 18px 18px', background: 'var(--c11141A)', border: '1px solid var(--c1F242D)', borderRadius: 16, boxShadow: 'inset 0 1px 0 color-mix(in srgb, var(--cFFFFFF) 3%, transparent), 0 24px 60px color-mix(in srgb, var(--c000000) 30%, transparent)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 15, fontWeight: 600 }}>Recent shifts</span>
          <span style={{ color: 'var(--cA3ABB9)', fontSize: 13 }}>Click any card to jump straight back to it</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="mono" style={{ fontSize: 12, color: 'var(--c7B8394)' }}>{hist.length} {hist.length === 1 ? 'shift' : 'shifts'}</span>
          <button type="button" className="cs-btn" onClick={clear} style={{ minHeight: 36, padding: '0 12px', borderRadius: 8, border: '1px solid var(--c2A303A)', background: 'transparent', color: 'var(--cC5CBD5)', fontSize: 13, cursor: 'pointer' }}>Clear</button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 14, overflowX: 'auto', padding: '2px 2px 6px' }}>
        {cards}
        {!hist.length && <div style={{ flex: 1, padding: 22, border: '1px dashed var(--c2A303A)', borderRadius: 12, color: 'var(--c7B8394)', textAlign: 'center' }}>Your translations will appear here as you shift.</div>}
      </div>
    </section>
  )
}
