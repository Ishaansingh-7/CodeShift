import { useState } from 'react'
import { LANG, LC, ORDER, fileOf } from '../lang.js'
import { tok, tokenColor } from '../highlight.js'
import { irRows } from './ResultTabs.jsx'
import AstTree from './AstTree.jsx'

const LIMIT = { tokens: 36, lines: 12, table: 6, code: 14, tree: 9999 }
const NOUN = ['tokens', 'tree nodes', 'symbols', 'IR lines', 'IR lines', 'lines']
const count = n => 1 + n.children.reduce((s, c) => s + count(c), 0)

export default function PipelineView({ ctx, toPlay }) {
  const { good, cfg } = ctx
  const [pst, setPst] = useState(0)
  const [open, setOpen] = useState({})
  if (!good) {
    return (
      <div style={{ margin: '48px 0', padding: 24, borderRadius: 16, background: '#11141A', border: '1px solid #1F242D', color: '#A3ABB9', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <span>Nothing to show yet. The pipeline view shows every stage of your last successful shift in the playground.</span>
        <button type="button" className="cs-btn" onClick={toPlay} style={{ minHeight: 40, padding: '0 16px', borderRadius: 8, border: '1px solid #FFA657', background: 'rgba(255,166,87,0.12)', color: '#FFA657', fontSize: 14, cursor: 'pointer' }}>Open the playground</button>
      </div>
    )
  }
  const src = good.src
  const tgt = good.tgt
  const srcFile = fileOf(src)
  const tgtFile = fileOf(tgt)
  const S = LANG[src].short
  const T = LANG[tgt].short
  const tokens = good.tokens
  const plain = irRows(good.ir, false)
  const opt = irRows(good.ir, true)
  const unOps = good.ir.filter(r => r.kind !== 'label' && r.tag !== '+').length
  const optOps = good.ir.filter(r => r.kind !== 'label' && (r.tag === '' || r.tag === '+')).length
  const nodes = good.ast ? count(good.ast) : 0
  const PD = [
    { name: 'Lexer', short: 'Text → tokens', input: srcFile, output: `${tokens.length} tokens`, kind: 'tokens', what: `Reads ${srcFile} character by character and groups it into tokens: keywords, names, numbers and operators. Whitespace is dropped, and each token keeps its line and column for error messages.` },
    { name: 'Parser', short: 'Tokens → AST', input: `${tokens.length} tokens`, output: `${nodes} AST nodes`, kind: 'tree', what: `A hand-written recursive-descent parser for ${S} checks the tokens against the grammar and builds a syntax tree. Syntax errors are reported with the exact line and column.` },
    { name: 'Semantic', short: 'Scopes & types', input: 'Syntax tree', output: `${good.symbols.length} symbols`, kind: 'table', what: `Builds a symbol table, checks every name is in scope, and assigns each value a type that ${T} can use` + (LANG[tgt].typing === 'static' ? ' in its declarations.' : `. ${T} is dynamically typed, so the types stay internal.`) },
    { name: 'IR', short: 'Shared core', input: 'Typed tree', output: `${unOps} IR ops`, kind: 'lines', lines: plain, what: 'The typed tree is lowered into three-address code: one simple operation per line with explicit jumps. This is the same representation no matter which of the six languages you started from.' },
    { name: 'Optimizer', short: 'Fold · CSE · copy-prop · DCE', input: `${unOps} IR ops`, output: cfg.optimize ? `${optOps} ops (−${unOps - optOps})` : 'skipped', kind: 'lines', lines: opt, what: cfg.optimize ? 'Constant folding, common-subexpression elimination, copy propagation and dead-code elimination clean up the IR, using dataflow over the control-flow graph. Struck-through lines were removed and green lines are their replacements.' : 'Optimize IR was off for this shift, so the IR went to the code generator unchanged. Shown here is what the passes would remove.' },
    { name: 'Codegen', short: `AST → ${T}`, input: `${cfg.optimize ? optOps : unOps} IR ops`, output: `${tgtFile} · ${good.tgtLines.length} lines`, kind: 'code', what: `The ${T} backend walks the typed tree and writes idiomatic ${T}: the right integer types, print call and entry point. This is exactly the output in your playground.` },
  ]
  const cur = PD[pst]
  const total = cur.kind === 'tokens' ? tokens.length : cur.kind === 'table' ? good.symbols.length : cur.kind === 'code' ? good.tgtLines.length : cur.kind === 'tree' ? nodes : cur.lines.length
  const lim = LIMIT[cur.kind]
  const can = total > lim + Math.ceil(lim / 3)
  const expanded = !!open[pst]
  const n = can && !expanded ? lim : total
  return (
    <>
      <section style={{ padding: '34px 0 22px', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span className="mono" style={{ fontSize: 12, letterSpacing: '0.14em', color: '#C792EA' }}>PIPELINE</span>
          <h1 style={{ margin: 0, fontSize: 'clamp(30px, 3.6vw, 44px)', fontWeight: 650, letterSpacing: '-0.025em' }}>How CodeShift <span style={{ color: '#FFA657' }}>works</span>.</h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="mono" style={{ fontSize: 12.5, padding: '10px 12px', borderRadius: 10, background: '#11141A', border: '1px solid #1F242D' }}>
            <span style={{ color: '#7B8394' }}>Showing your last shift · </span><span style={{ color: '#6CB6FF' }}>{srcFile}</span><span style={{ color: '#7B8394' }}> → </span><span style={{ color: '#FFA657' }}>{tgtFile}</span>
          </span>
          <button type="button" className="cs-btn" onClick={toPlay} style={{ minHeight: 42, padding: '0 14px', borderRadius: 10, border: '1px solid #2A303A', background: 'transparent', color: '#C5CBD5', fontSize: 13.5, cursor: 'pointer' }}>Back to playground</button>
        </div>
      </section>

      <div role="group" aria-label="Stages" className="pp-rail" style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
        {PD.map((d, i) => {
          const on = i === pst
          const done = i < pst
          return [
            <button key={d.name} type="button" className="pp-stage" aria-pressed={on} onClick={() => setPst(i)}
              style={{ flex: '1 1 0', minWidth: 0, textAlign: 'left', padding: '14px 12px', borderRadius: 14, border: `1px solid ${on ? '#FFA657' : '#1F242D'}`, background: on ? 'rgba(255,166,87,0.08)' : '#11141A', color: '#E6E9EF', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 8, boxShadow: on ? '0 14px 34px rgba(255,166,87,0.16)' : 'none' }}>
              <span className="mono" style={{ width: 26, height: 26, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 600, background: on ? '#FFA657' : done ? 'rgba(126,231,135,0.16)' : '#1A1E26', color: on ? '#1A1006' : done ? '#7EE787' : '#A3ABB9' }}>{i + 1}</span>
              <span style={{ fontSize: 15, fontWeight: 600 }}>{d.name}</span>
              <span style={{ fontSize: 12.5, color: '#A3ABB9' }}>{d.short}</span>
            </button>,
            i < PD.length - 1 && <span key={d.name + '-arrow'} className="pp-arrow" aria-hidden="true" style={{ alignSelf: 'center', color: '#4A5260', fontSize: 18 }}>→</span>,
          ]
        })}
      </div>

      <section aria-label="Stage detail" style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ flex: cur.kind === 'tree' ? '1 1 100%' : '1 1 380px', minWidth: 0, padding: 22, borderRadius: 16, background: '#11141A', border: '1px solid #1F242D', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <span className="mono" style={{ fontSize: 12, letterSpacing: '0.12em', color: '#FFA657' }}>STAGE {pst + 1} OF 6</span>
          <h2 style={{ margin: 0, fontSize: 26, fontWeight: 650, letterSpacing: '-0.02em' }}>{cur.name}</h2>
          <p style={{ margin: 0, maxWidth: 760, color: '#C5CBD5', fontSize: 15, lineHeight: 1.65 }}>{cur.what}</p>
          <div className="mono" style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', fontSize: 12.5 }}>
            <span style={{ padding: '6px 10px', borderRadius: 8, background: 'rgba(108,182,255,0.12)', color: '#6CB6FF' }}>{cur.input}</span>
            <span style={{ color: '#7B8394' }}>→</span>
            <span style={{ padding: '6px 10px', borderRadius: 8, background: 'rgba(255,166,87,0.12)', color: '#FFA657' }}>{cur.output}</span>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
            <button type="button" className="cs-btn" onClick={() => setPst((pst + 5) % 6)} style={{ minHeight: 44, padding: '0 14px', borderRadius: 10, border: '1px solid #2A303A', background: 'transparent', color: '#C5CBD5', fontSize: 13.5, cursor: 'pointer' }}>← Previous</button>
            <button type="button" className="cs-btn" onClick={() => setPst((pst + 1) % 6)} style={{ minHeight: 44, padding: '0 16px', borderRadius: 10, border: 'none', background: '#FFA657', color: '#1A1006', fontSize: 13.5, fontWeight: 600, cursor: 'pointer' }}>Next stage →</button>
          </div>
        </div>
        <div style={{ flex: '1.3 1 480px', minWidth: 0, borderRadius: 16, background: '#11141A', border: '1px solid #1F242D', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, padding: '12px 16px', borderBottom: '1px solid #1F242D' }}>
            <span className="mono" style={{ fontSize: 12.5, color: '#E6E9EF' }}>Your code · {srcFile} → {tgtFile}</span>
            <span className="mono" style={{ fontSize: 11, color: '#7B8394' }}>{cur.output}</span>
          </div>
          <Detail kind={cur.kind} key={pst} good={good} n={n} lines={cur.lines} file={srcFile} />
          {can && !expanded && <div aria-hidden="true" style={{ position: 'relative', height: 48, marginTop: -48, background: 'linear-gradient(rgba(17,20,26,0), #11141A)', pointerEvents: 'none' }} />}
          {can && (
            <button type="button" className="cs-btn" aria-expanded={expanded} onClick={() => setOpen({ ...open, [pst]: !expanded })}
              style={{ width: '100%', minHeight: 46, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, border: 'none', borderTop: '1px solid #1F242D', background: '#0E1116', color: '#C5CBD5', fontFamily: 'inherit', fontSize: 13, cursor: 'pointer' }}>
              <span>{expanded ? `Show fewer ${NOUN[pst]}` : `Show all ${total} ${NOUN[pst]}`}</span>
              <span className="mono" style={{ fontSize: 11, padding: '2px 7px', borderRadius: 6, background: '#1A1E26', color: '#FFA657' }}>{expanded ? `all ${total}` : `+${total - lim} hidden`}</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ transform: `rotate(${expanded ? 180 : 0}deg)`, transition: 'transform .2s ease' }}><path d="M6 9l6 6 6-6" /></svg>
            </button>
          )}
        </div>
      </section>

      <section aria-label="Shared core" style={{ marginTop: 40, padding: 28, borderRadius: 20, background: '#11141A', border: '1px solid #1F242D' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 620 }}>
            <h2 style={{ margin: 0, fontSize: 26, fontWeight: 650, letterSpacing: '-0.02em' }}>One core, every path</h2>
            <p style={{ margin: 0, color: '#A3ABB9', fontSize: 15, lineHeight: 1.6 }}>Six frontends read code into the shared IR and six backends write it back out: 12 components instead of 30 pair-by-pair translators.</p>
          </div>
          <span className="mono" style={{ fontSize: 13, color: '#C5CBD5', padding: '8px 12px', borderRadius: 10, background: '#0B0D12', border: '1px solid #1F242D' }}>6 + 6 = 12 <span style={{ color: '#7B8394' }}>vs</span> 6 × 5 = 30</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 40px auto 40px minmax(0, 1fr)', alignItems: 'center', gap: 10, marginTop: 26 }}>
          <Side title="FRONTENDS" color="#6CB6FF" pick={src} mine="your source" other="lexer + parser" />
          <span aria-hidden="true" style={{ textAlign: 'center', color: '#4A5260', fontSize: 22 }}>→</span>
          <div style={{ width: 150, height: 150, borderRadius: '50%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4, background: '#14101C', border: '1px solid rgba(199,146,234,0.45)', boxShadow: '0 0 0 10px rgba(199,146,234,0.06), 0 0 50px rgba(199,146,234,0.18)' }}>
            <span className="mono" style={{ fontSize: 30, fontWeight: 700, color: '#C792EA' }}>IR</span>
            <span style={{ fontSize: 11, letterSpacing: '0.12em', color: '#A3ABB9' }}>SHARED CORE</span>
            <span className="mono" style={{ fontSize: 10.5, color: '#7B8394' }}>{cfg.optimize ? optOps : unOps} ops</span>
          </div>
          <span aria-hidden="true" style={{ textAlign: 'center', color: '#4A5260', fontSize: 22 }}>→</span>
          <Side title="BACKENDS" color="#FFA657" pick={tgt} mine="your target" other="codegen" />
        </div>
      </section>
    </>
  )
}

function Side({ title, color, pick, mine, other }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span className="mono" style={{ fontSize: 11, letterSpacing: '0.14em', color }}>{title}</span>
      {ORDER.map(l => (
        <span key={l} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '9px 12px', borderRadius: 10, background: '#0E1116', border: `1px solid ${l === pick ? color : '#1F242D'}`, fontSize: 13.5 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: LC[l] }} />{LANG[l].short}</span>
          <span className="mono" style={{ fontSize: 11, color: l === pick ? color : '#7B8394' }}>{l === pick ? mine : other}</span>
        </span>
      ))}
    </div>
  )
}

function Detail({ kind, good, n, lines, file }) {
  if (kind === 'tokens') {
    return (
      <div style={{ padding: 18, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {good.tokens.slice(0, n).map((t, i) => (
          <span key={i} className="cs-up mono" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 8, background: '#161A21', border: '1px solid #262B34', fontSize: 12.5, animationDelay: `${Math.min(i * 18, 600)}ms` }}>
            <span style={{ color: '#7B8394', fontSize: 10.5 }}>{t.kind}</span>
            <span style={{ color: tokenColor(t.kind) }}>{t.kind === 'NEWLINE' ? '↵' : t.kind === 'INDENT' ? '→' : t.kind === 'DEDENT' ? '←' : t.text}</span>
          </span>
        ))}
      </div>
    )
  }
  if (kind === 'tree') return good.ast ? <AstTree ast={good.ast} file={file} /> : null
  if (kind === 'table') {
    return (
      <div style={{ padding: '10px 16px 16px', overflowX: 'auto' }}>
        <div className="mono" style={{ minWidth: 440, fontSize: 13 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12, padding: '8px 0', color: '#7B8394', fontSize: 11.5, borderBottom: '1px solid #1F242D' }}><span>NAME</span><span>KIND</span><span>TYPE</span><span>SCOPE</span></div>
          {good.symbols.slice(0, n).map((r, i) => (
            <div key={i} className="cs-up" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12, padding: '9px 0', borderBottom: '1px solid #171B22', animationDelay: `${i * 60}ms` }}>
              <span style={{ color: '#82AAFF' }}>{r.name}</span><span style={{ color: '#A3ABB9' }}>{r.kind}</span><span style={{ color: '#7FDBCA' }}>{r.type}</span><span style={{ color: '#A3ABB9' }}>{r.scope}</span>
            </div>
          ))}
        </div>
      </div>
    )
  }
  if (kind === 'lines') {
    return (
      <div className="mono" style={{ padding: '14px 0', fontSize: 13, lineHeight: '22px', overflowX: 'auto' }}>
        {lines.slice(0, n).map((l, i) => (
          <div key={i} className="cs-in" style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '0 16px', whiteSpace: 'pre', background: l.bg, animationDelay: `${Math.min(i * 30, 600)}ms` }}>
            <span style={{ color: l.c, textDecoration: l.deco }}>{l.t}</span><span style={{ fontSize: 11, color: l.tagColor }}>{l.tag}</span>
          </div>
        ))}
      </div>
    )
  }
  return (
    <div className="mono" style={{ padding: '12px 0', fontSize: 13, lineHeight: '22px', overflowX: 'auto' }}>
      {good.tgtLines.slice(0, n).map((r, i) => (
        <div key={i} className="cs-in" style={{ display: 'flex', minHeight: 22, animationDelay: `${Math.min(i * 30, 600)}ms` }}>
          <span style={{ width: 44, flex: 'none', textAlign: 'right', paddingRight: 16, boxSizing: 'border-box', color: '#4A5260', userSelect: 'none' }}>{i + 1}</span>
          <span style={{ whiteSpace: 'pre' }}>{tok(r.text).map((t, j) => <span key={j} style={{ color: t.c }}>{t.t}</span>)}</span>
        </div>
      ))}
    </div>
  )
}
