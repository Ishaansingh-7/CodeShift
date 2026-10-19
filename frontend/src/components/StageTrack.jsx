import { STAGES } from '../lang.js'

const FAIL = { lexer: 0, parser: 1, semantic: 2, harness: 2, codegen: 5, pipeline: 0, network: 0 }
const BASE = { width: 28, height: 28, flex: 'none', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', boxSizing: 'border-box', fontFamily: "'JetBrains Mono', monospace", fontSize: 11, transition: 'background .3s ease, border-color .3s ease, box-shadow .3s ease' }
const DOT = {
  done: { background: '#15241A', color: '#7EE787', border: '1px solid #2F6B3C' },
  active: { background: '#2A1E10', color: '#FFA657', border: '1px solid #FFA657', boxShadow: '0 0 0 5px rgba(255,166,87,0.14), 0 0 22px rgba(255,166,87,0.45)' },
  skipped: { background: '#0E1116', color: '#5E6674', border: '1px dashed #3A404C' },
  pending: { background: '#0E1116', color: '#5E6674', border: '1px solid #2A303A' },
  blocked: { background: '#2A2410', color: '#FFCB6B', border: '1px dashed #FFCB6B' },
  failed: { background: '#2A1414', color: '#FF8F85', border: '1px solid #FF8F85', boxShadow: '0 0 0 5px rgba(255,143,133,0.12)' },
}

export default function StageTrack({ ctx }) {
  const { busy, phase, result, error, blocked, empty, cfg } = ctx
  const s = result?.stats || {}
  const fail = error && !empty ? (blocked ? 5 : FAIL[error.stage] ?? 0) : -1
  const meta = [`${s.tokens ?? 0} tokens`, 'AST ok', result?.types.length ? `${result.types.length} types` : 'dynamic',
    `${s.irOps ?? 0} ops`, cfg.optimize ? `−${s.removed ?? 0} ops` : 'off', `${s.lines ?? 0} lines`]
  const states = STAGES.map((_, i) => {
    if (busy) return i < phase ? 'done' : i === phase ? 'active' : 'pending'
    if (empty) return 'pending'
    if (fail >= 0) return i < fail ? 'done' : i === fail ? (blocked ? 'blocked' : 'failed') : 'pending'
    if (i === 4 && !cfg.optimize) return 'skipped'
    return result ? 'done' : 'pending'
  })
  const pct = empty && !busy ? '0%' : busy ? `${Math.round(Math.min(phase, 5) / 5 * 100)}%` : fail >= 0 ? `${fail / 5 * 100}%` : '100%'
  const color = busy ? '#FFA657' : blocked && !empty ? '#FFCB6B' : fail >= 0 ? '#FF8F85' : 'rgba(126,231,135,0.55)'
  return (
    <div aria-label="Compiler stages" style={{ position: 'relative', marginTop: 14, padding: '16px 14px 14px', background: 'rgba(14,17,22,0.9)', border: '1px solid #1B1F27', borderRadius: 14, overflow: 'hidden' }}>
      <div className="cs-track" aria-hidden="true" style={{ position: 'absolute', left: 'calc(14px + (100% - 28px) / 12)', right: 'calc(14px + (100% - 28px) / 12)', top: 29, height: 2, borderRadius: 2, background: '#232833' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, height: 2, borderRadius: 2, width: pct, background: color, transition: 'width .17s linear, background .4s ease' }} />
        {busy && <span style={{ position: 'absolute', top: -5, left: pct, width: 12, height: 12, marginLeft: -6, borderRadius: '50%', background: '#FFA657', boxShadow: '0 0 0 4px rgba(255,166,87,0.18), 0 0 18px rgba(255,166,87,0.85)', transition: 'left .17s linear' }} />}
      </div>
      <div className="cs-stages" style={{ position: 'relative', display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', gap: '14px 0' }}>
        {STAGES.map((name, i) => {
          const st = states[i]
          return (
            <div key={name} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7, minWidth: 0, textAlign: 'center' }}>
              <span className={st === 'pending' ? '' : 'cs-pop'} style={{ ...BASE, ...DOT[st] }}>
                {st === 'done' ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10" /></svg>
                  : st === 'skipped' || st === 'blocked' ? '–' : st === 'failed' ? '!' : i + 1}
              </span>
              <span style={{ fontSize: 13, fontWeight: 600, color: st === 'pending' || st === 'skipped' ? '#7B8394' : st === 'failed' ? '#FF8F85' : st === 'blocked' ? '#FFCB6B' : '#E6E9EF' }}>{name}</span>
              <span className="mono" style={{ fontSize: 11, color: '#7B8394', whiteSpace: 'nowrap' }}>
                {st === 'pending' ? 'waiting' : st === 'active' ? 'running…' : st === 'failed' ? 'error' : st === 'blocked' ? 'not supported' : meta[i]}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
