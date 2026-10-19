import { useState } from 'react'
import { LANG } from '../lang.js'
import { tokenColor } from '../highlight.js'
import CfgGraph from './CfgGraph.jsx'

const CARD = { background: '#0E1116', border: '1px solid #1F242D', borderRadius: 12, padding: 16 }
const MUTED = { color: '#7B8394', fontSize: 12, marginTop: 4 }
const Tick = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10" /></svg>
const Cross = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 6l12 12" /><path d="M18 6L6 18" /></svg>
const Spin = () => <svg className="cs-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9" /></svg>

export function irRows(ir, optimize) {
  const color = k => k === 'label' ? '#6CB6FF' : k === 'jump' ? '#C792EA' : '#DDE1E7'
  return ir.filter(r => optimize || r.tag !== '+').map(r => {
    const dropped = optimize && r.tag && r.tag !== '+'
    const added = optimize && r.tag === '+'
    return { t: r.text, c: dropped ? '#5E6674' : added ? '#7EE787' : color(r.kind), deco: dropped ? 'line-through' : 'none',
      bg: added ? 'rgba(126,231,135,0.08)' : dropped ? 'rgba(255,143,133,0.05)' : 'transparent', tag: dropped ? r.tag : added ? 'new' : '',
      tagColor: added ? '#7EE787' : '#FF8F85' }
  })
}

function RunTab({ ctx, rerun }) {
  const { cfg, diff, ran, error, blocked, empty, busy, rev, stdin, setStdin } = ctx
  const rows = diff?.rows || []
  const pending = !error && !empty && (busy || rev >= 0 || !diff)
  const shown = pending ? 0 : Math.min(ran, rows.length)
  const matches = rows.slice(0, shown).filter(r => r.match).length
  const reasons = {}
  rows.slice(0, shown).filter(r => !r.match).forEach(r => { reasons[r.reason] = (reasons[r.reason] || 0) + 1 })
  const fails = Object.entries(reasons).map(([k, n]) => `${n} ${k}`).join(' · ')
  const placeholder = pending ? Array.from({ length: 5 }, (_, k) => ({ input: '…', srcOut: '…', tgtOut: '…', pending: true, k })) : []
  const list = pending ? placeholder : rows.map((r, k) => ({ ...r, pending: k >= shown, k }))
  const total = pending ? 5 : rows.length
  const matchText = pending || shown < rows.length ? `running ${shown} / ${total}` : `${matches} / ${rows.length} match`
  const program = diff?.program
  return (
    <div className="cs-up" style={{ padding: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Differential test</div>
          <div style={{ color: '#A3ABB9', marginTop: 4 }}>The same inputs run through the {LANG[cfg.src].short} source and the {LANG[cfg.tgt].short} output, and the results are compared.</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {!error && rows.length > 0 || pending ? <span className="mono" style={{ fontSize: 12, color: '#7EE787', background: 'rgba(126,231,135,0.10)', padding: '6px 10px', borderRadius: 8 }}>{matchText}</span> : null}
          {fails && <span className="mono" style={{ fontSize: 12, color: '#FF8F85', background: 'rgba(255,143,133,0.12)', padding: '6px 10px', borderRadius: 8 }}>{fails}</span>}
          <button type="button" className="cs-btn" onClick={rerun} style={{ minHeight: 36, padding: '0 12px', borderRadius: 8, border: '1px solid #2A303A', background: 'transparent', color: '#C5CBD5', fontSize: 13, cursor: 'pointer' }}>Re-run</button>
        </div>
      </div>
      <div style={{ marginBottom: 14 }}>
        <label htmlFor="cs-stdin" style={{ display: 'block', fontSize: 12, color: '#7B8394', marginBottom: 6 }}>Standard input · fed to both programs</label>
        <textarea id="cs-stdin" className="mono" value={stdin} onChange={e => setStdin(e.target.value)} rows={stdin.split('\n').length > 2 ? 4 : 2} spellCheck={false}
          placeholder="Lines your program reads with input(), scanf, readLine() …"
          style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', background: '#0B0E13', color: '#E6E9EF', border: '1px solid #2A303A', borderRadius: 8, padding: '10px 12px', fontSize: 13, lineHeight: 1.5, outline: 'none' }} />
      </div>
      {empty ? (
        <div style={{ ...CARD, color: '#C5CBD5' }}>Nothing to run yet. Write a program in the editor and it is tested as soon as it shifts.</div>
      ) : blocked ? (
        <div style={{ ...CARD, color: '#C5CBD5', lineHeight: 1.6 }}>This program can't be translated to {LANG[cfg.tgt].short} yet, so nothing was run. <span className="mono" style={{ color: '#FFCB6B' }}>{error.message}</span></div>
      ) : error ? (
        <div style={{ ...CARD, color: '#C5CBD5' }}>The source does not compile yet, so nothing was run. Fix <span className="mono" style={{ color: '#FF8F85' }}>{error.message}</span> and the tests run again.</div>
      ) : !pending && !rows.length ? (
        <div style={{ ...CARD, color: '#C5CBD5', lineHeight: 1.6 }}>No per-input test for this code: {diff?.errors[0]?.message || 'no inputs'}. The whole programs are still compared below.</div>
      ) : (
        <div style={{ overflowX: 'auto', border: '1px solid #1F242D', borderRadius: 12 }}>
          <div className="mono" style={{ minWidth: 640, fontSize: 13 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12, padding: '10px 14px', background: '#0E1116', color: '#7B8394', fontSize: 12 }}>
              <span>{diff?.label || 'Input'}</span><span>{LANG[cfg.src].run}</span><span>{LANG[cfg.tgt].run}</span><span>Result</span>
            </div>
            {list.map(r => (
              <div key={r.k} className="cs-row cs-up" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12, padding: '11px 14px', borderTop: '1px solid #1B1F27', animationDelay: `${r.k * 60}ms` }}>
                <span style={{ color: '#C5CBD5', wordBreak: 'break-all' }}>{r.input}</span>
                <span style={{ wordBreak: 'break-all', color: r.pending ? '#5E6674' : '#E6E9EF' }}>{r.pending ? '…' : r.srcOut === '' ? '(empty line)' : r.srcOut}</span>
                <span style={{ wordBreak: 'break-all', color: r.pending ? '#5E6674' : r.match ? '#E6E9EF' : '#FF8F85' }}>{r.pending ? '…' : r.tgtOut === '' ? '(empty line)' : r.tgtOut}</span>
                <span>
                  {r.pending ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: '#A3ABB9' }}><Spin />running</span>
                    : r.match ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#7EE787' }}><Tick />match</span>
                      : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#FF8F85' }}><Cross />{r.reason}</span>}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {!error && !empty && program && !pending && (
        <div className="mono cs-up" style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center', marginTop: 12, fontSize: 12, color: '#A3ABB9' }}>
          <span style={{ color: '#7B8394' }}>Whole program</span>
          <span>{LANG[cfg.src].short}: <span style={{ color: '#E6E9EF' }}>{program.srcStatus === 'ok' ? program.srcOut.trim() || '(no output)' : program.srcStatus}</span></span>
          <span>{LANG[cfg.tgt].short}: <span style={{ color: '#E6E9EF' }}>{program.tgtStatus === 'ok' ? program.tgtOut.trim() || '(no output)' : program.tgtStatus}</span></span>
          <span style={{ color: program.match ? '#7EE787' : '#FF8F85' }}>{program.match ? 'same output' : 'output differs'}</span>
        </div>
      )}
    </div>
  )
}

function ReportTab({ ctx }) {
  const { shown, error, blocked, stale } = ctx
  const bad = blocked ? '#FFCB6B' : '#FF8F85'
  const changed = shown?.changed || []
  const approx = shown?.approx || []
  const library = shown?.library || []
  const imports = shown?.imports || []
  const types = shown?.types?.length ? shown.types : ['dynamic · types erased']
  return (
    <div className={'cs-up' + (stale ? ' cs-stale' : '')} style={{ padding: 20, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14 }}>
      <div style={CARD}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}><span style={{ fontWeight: 600 }}>Changed</span><span className="mono" style={{ fontSize: 12, color: '#6CB6FF' }}>{changed.length}</span></div>
        {changed.map((c, i) => (
          <div key={i} style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #1B1F27' }}>
            <div style={{ color: '#7B8394', fontSize: 11, letterSpacing: '0.08em' }}>{c.where}</div>
            <div className="mono" style={{ fontSize: 12, color: '#C3E88D', marginTop: 6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{c.from}</div>
            <div className="mono" style={{ fontSize: 12, color: '#FFCB6B', marginTop: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>→ {c.to}</div>
          </div>
        ))}
      </div>
      <div style={CARD}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}><span style={{ fontWeight: 600 }}>Approximated</span><span className="mono" style={{ fontSize: 12, color: '#FFA657' }}>{approx.length}</span></div>
        {approx.map((a, i) => (
          <div key={i} style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #1B1F27' }}>
            <div className="mono" style={{ fontSize: 12, color: '#C3E88D' }}>{a.from}</div>
            <div className="mono" style={{ fontSize: 12, color: '#FFCB6B', marginTop: 4 }}>→ {a.to}</div>
            <div style={{ color: '#C5CBD5', fontSize: 13, marginTop: 8, lineHeight: 1.5 }}>{a.note}</div>
          </div>
        ))}
        {!approx.length && <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #1B1F27', color: '#C5CBD5', lineHeight: 1.5 }}>Both languages share the same integer and division rules here, so nothing had to be approximated.</div>}
        <div style={{ fontWeight: 600, marginTop: 20 }}>Types in output</div>
        <div className="mono" style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10, fontSize: 12 }}>
          {types.map(t => <span key={t} style={{ background: '#1A1E26', padding: '5px 8px', borderRadius: 6 }}>{t}</span>)}
        </div>
      </div>
      <div style={CARD}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}><span style={{ fontWeight: 600 }}>Library</span><span className="mono" style={{ fontSize: 12, color: '#C792EA' }}>{library.length}</span></div>
        {library.map((l, i) => (
          <div key={i} style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #1B1F27' }}>
            <div className="mono" style={{ color: '#7B8394', fontSize: 11, letterSpacing: '0.04em' }}>{l.call}</div>
            <div className="mono" style={{ fontSize: 12, color: '#C3E88D', marginTop: 6, wordBreak: 'break-word' }}>{l.from}</div>
            <div className="mono" style={{ fontSize: 12, color: '#FFCB6B', marginTop: 4, wordBreak: 'break-word' }}>→ {l.to}</div>
          </div>
        ))}
        {!library.length && <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #1B1F27', color: '#C5CBD5', lineHeight: 1.5 }}>No library calls: everything here is core syntax.</div>}
        <div style={{ fontWeight: 600, marginTop: 20 }}>Imports added</div>
        <div className="mono" style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10, fontSize: 12 }}>
          {imports.length ? imports.map(t => <span key={t} style={{ background: '#1A1E26', padding: '5px 8px', borderRadius: 6 }}>{t}</span>) : <span style={{ color: '#7B8394' }}>none</span>}
        </div>
      </div>
      <div style={CARD}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}><span style={{ fontWeight: 600 }}>Unsupported</span><span className="mono" style={{ fontSize: 12, color: error ? bad : '#7EE787' }}>{error ? 1 : 0}</span></div>
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #1B1F27', color: '#C5CBD5', lineHeight: 1.5 }}>
          {error ? <span className="mono" style={{ color: bad, fontSize: 12.5 }}>{error.message}</span> : 'Every construct in this program is inside the supported subset.'}
        </div>
        <div style={{ marginTop: 14, color: '#7B8394', fontSize: 12, lineHeight: 1.6 }}>Outside the subset (flagged, never guessed): classes, exceptions, generators, regular expressions, random numbers, dates, JSON, threads, files, pointer arithmetic.</div>
      </div>
    </div>
  )
}

function CompilerTab({ ctx }) {
  const { shown, cfg, stale } = ctx
  const tokens = (shown?.tokens || []).filter(t => t.line <= 3 && t.kind !== 'EOF')
  const ir = irRows(shown?.ir || [], cfg.optimize)
  const ops = shown?.stats.irOps ?? 0
  return (
    <div className={'cs-up' + (stale ? ' cs-stale' : '')} style={{ padding: 20 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
        <div style={{ ...CARD, flex: '1 1 380px', minWidth: 0 }}>
          <div style={{ fontWeight: 600 }}>Token stream</div>
          <div style={MUTED}>From the hand-written {LANG[cfg.src].short} lexer, lines 1–3</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
            {tokens.map((t, i) => (
              <span key={i} className="cs-up mono" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: '#161A21', border: '1px solid #262B34', borderRadius: 6, padding: '4px 8px', fontSize: 11, animationDelay: `${Math.min(i * 25, 600)}ms` }}>
                <span style={{ color: '#7B8394' }}>{t.kind}</span><span style={{ color: tokenColor(t.kind) }}>{t.kind === 'NEWLINE' ? '↵' : t.kind === 'INDENT' ? '→' : t.kind === 'DEDENT' ? '←' : t.text}</span>
              </span>
            ))}
          </div>
        </div>
        <div style={{ ...CARD, flex: '1 1 380px', minWidth: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontWeight: 600 }}>Three-address IR</div>
              <div style={MUTED}>Shared by every backend · {ops} ops</div>
            </div>
            <span className="mono" style={{ fontSize: 11, color: cfg.optimize ? '#7EE787' : '#A3ABB9', border: `1px solid ${cfg.optimize ? 'rgba(126,231,135,0.35)' : '#2A303A'}`, borderRadius: 999, padding: '4px 9px' }}>
              {cfg.optimize ? `optimized · −${shown?.stats.removed ?? 0} ops` : 'unoptimized'}
            </span>
          </div>
          <div className="mono" style={{ marginTop: 14, fontSize: 12.5, lineHeight: '22px', maxHeight: 520, overflow: 'auto' }}>
            {ir.map((r, i) => (
              <div key={i} className="cs-in" style={{ whiteSpace: 'pre', display: 'flex', justifyContent: 'space-between', gap: 12, padding: '0 10px', borderRadius: 6, color: r.c, background: r.bg, animationDelay: `${Math.min(i * 30, 600)}ms` }}>
                <span style={{ textDecoration: r.deco }}>{r.t}</span><span style={{ fontSize: 10.5, color: r.tagColor }}>{r.tag}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function CfgTab({ ctx }) {
  const { shown, stale } = ctx
  const blocks = shown?.cfg.blocks || []
  const fns = [...new Set(blocks.map(b => b.fn))]
  const [fn, setFn] = useState(fns[0])
  const cur = fns.includes(fn) ? fn : fns[0]
  const mine = blocks.filter(b => b.fn === cur)
  const ids = new Set(mine.map(b => b.id))
  const edges = (shown?.cfg.edges || []).filter(e => ids.has(e.from))
  return (
    <div className={stale ? 'cs-stale' : ''} style={{ padding: '20px 20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Control-flow graph</div>
          <div style={{ color: '#A3ABB9', marginTop: 4 }}>Basic blocks of the {ctx.cfg.optimize ? 'optimized' : 'unoptimized'} IR. Edges are labelled true, false and back.</div>
        </div>
        <div role="group" aria-label="Function" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {fns.map(f => (
            <button key={f} type="button" className="cs-btn mono" aria-pressed={f === cur} onClick={() => setFn(f)}
              style={{ minHeight: 34, padding: '0 12px', borderRadius: 8, fontSize: 12, cursor: 'pointer', background: f === cur ? 'rgba(255,166,87,0.12)' : 'transparent', color: f === cur ? '#FFA657' : '#A3ABB9', border: `1px solid ${f === cur ? 'rgba(255,166,87,0.45)' : '#2A303A'}` }}>
              {f}()
            </button>
          ))}
        </div>
      </div>
      <div style={{ overflowX: 'auto', paddingBottom: 6 }}>
        <CfgGraph blocks={mine} edges={edges} />
      </div>
    </div>
  )
}

export default function ResultTabs({ ctx, rerun }) {
  const { tab, setTab, diff, ran, shown, error, empty, busy, rev } = ctx
  const rows = diff?.rows || []
  const done = !error && !busy && rev < 0 && diff
  const shownRows = done ? Math.min(ran, rows.length) : 0
  const matches = rows.slice(0, shownRows).filter(r => r.match).length
  const tabs = [
    ['run', 'Run & test', error || empty ? '' : !done || shownRows < rows.length ? `${shownRows}/${rows.length || 5} …` : rows.length ? `${matches}/${rows.length}` : ''],
    ['report', 'Shift report', shown ? String(shown.changed.length + shown.approx.length + (shown.library || []).length) : ''],
    ['compiler', 'Compiler view', ''],
    ['cfg', 'Control flow', ''],
  ]
  return (
    <section style={{ marginTop: 16, background: '#11141A', border: '1px solid #1F242D', borderRadius: 16, overflow: 'hidden', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)' }}>
      <div role="tablist" aria-label="Results" style={{ display: 'flex', gap: 4, flexWrap: 'wrap', padding: '8px 8px 0', borderBottom: '1px solid #1F242D' }}>
        {tabs.map(([id, label, badge]) => {
          const on = id === tab
          return (
            <button key={id} type="button" className="cs-btn" role="tab" aria-selected={on} onClick={() => setTab(id)}
              style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 44, padding: '0 16px', background: 'transparent', border: 'none', borderBottom: `2px solid ${on ? '#FFA657' : 'transparent'}`, color: on ? '#FFFFFF' : '#A3ABB9', fontSize: 14, fontWeight: on ? 600 : 500, cursor: 'pointer', marginBottom: -1, transition: 'color .15s ease, border-color .2s ease' }}>
              {label}
              {badge && <span className="mono" style={{ fontSize: 11, padding: '2px 6px', borderRadius: 5, background: on ? 'rgba(255,166,87,0.16)' : '#1A1E26', color: on ? '#FFA657' : '#A3ABB9' }}>{badge}</span>}
            </button>
          )
        })}
      </div>
      {tab === 'run' && <RunTab ctx={ctx} rerun={rerun} />}
      {tab === 'report' && <ReportTab ctx={ctx} />}
      {tab === 'compiler' && <CompilerTab ctx={ctx} />}
      {tab === 'cfg' && <CfgTab ctx={ctx} />}
    </section>
  )
}
