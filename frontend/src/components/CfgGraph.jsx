const CW = 7.4
const LH = 18
const VGAP = 58
const HGAP = 40
const PAD = 24
const LABEL = { true: '#7EE787', false: '#FF8F85', back: '#C792EA', '': '#4A5260' }

function layout(blocks, edges) {
  const index = new Map(blocks.map((b, i) => [b.id, i]))
  const forward = edges.filter(e => e.label !== 'back' && index.get(e.to) > index.get(e.from))
  const layer = blocks.map(() => 0)
  blocks.forEach((b, i) => forward.filter(e => e.from === b.id).forEach(e => {
    const j = index.get(e.to)
    layer[j] = Math.max(layer[j], layer[i] + 1)
  }))
  const size = blocks.map(b => {
    const longest = Math.max(b.title.length, ...b.lines.map(l => l.length))
    return { w: Math.max(170, Math.round(longest * CW) + 28), h: 40 + Math.max(1, b.lines.length) * LH }
  })
  const rows = []
  blocks.forEach((b, i) => (rows[layer[i]] ||= []).push(i))
  const widths = rows.map(r => r.reduce((s, i) => s + size[i].w, 0) + HGAP * (r.length - 1))
  const widest = Math.max(...widths)
  const pos = []
  let y = 0
  rows.forEach((r, k) => {
    let x = (widest - widths[k]) / 2
    r.forEach(i => { pos[i] = { x, y, ...size[i] }; x += size[i].w + HGAP })
    y += Math.max(...r.map(i => size[i].h)) + VGAP
  })
  return { pos, index, layer, H: y - VGAP }
}

function route(edges, pos, index, layer) {
  const live = edges.filter(e => index.has(e.from) && index.has(e.to))
  const kind = e => {
    const i = index.get(e.from), j = index.get(e.to)
    if (e.label === 'back' || pos[j].y <= pos[i].y) return 'back'
    return layer[j] - layer[i] > 1 ? 'skip' : 'down'
  }
  const extent = (e, side) => {
    const a = pos[index.get(e.from)], b = pos[index.get(e.to)]
    const lo = Math.min(a.y, b.y), hi = Math.max(a.y + a.h, b.y + b.h)
    const near = pos.filter(p => p.y < hi && p.y + p.h > lo)
    return side === 'right' ? Math.max(...near.map(p => p.x + p.w)) : Math.min(...near.map(p => p.x))
  }
  const height = e => Math.abs(pos[index.get(e.from)].y - pos[index.get(e.to)].y)
  const nest = {}
  for (const k of ['back', 'skip']) {
    live.filter(e => kind(e) === k).sort((a, b) => height(a) - height(b)).forEach((e, n) => { nest[live.indexOf(e)] = n })
  }
  return live.map((e, k) => {
    const a = pos[index.get(e.from)], b = pos[index.get(e.to)]
    const t = kind(e)
    if (t === 'down') {
      const x1 = a.x + a.w / 2, y1 = a.y + a.h, x2 = b.x + b.w / 2, y2 = b.y - 6
      return { k, label: e.label, d: `M ${x1} ${y1} C ${x1} ${y1 + VGAP / 2}, ${x2} ${y2 - VGAP / 2}, ${x2} ${y2}`, lx: (x1 + x2) / 2 + 6, ly: (y1 + y2) / 2, xs: [x1, x2] }
    }
    const right = t === 'back'
    const y1 = a.y + a.h / 2, y2 = b.y + b.h / 2
    const x1 = right ? a.x + a.w : a.x
    const x2 = right ? b.x + b.w + 6 : b.x - 6
    const bulge = right ? extent(e, 'right') + 30 + nest[k] * 18 : extent(e, 'left') - 30 - nest[k] * 18
    return { k, label: e.label, d: `M ${x1} ${y1} C ${bulge} ${y1}, ${bulge} ${y2}, ${x2} ${y2}`, lx: right ? bulge - 8 : bulge - 34, ly: (y1 + y2) / 2, xs: [bulge - 40, bulge + 40] }
  })
}

export default function CfgGraph({ blocks, edges }) {
  if (!blocks.length) return null
  const { pos, index, layer, H } = layout(blocks, edges)
  const paths = route(edges, pos, index, layer)
  const xs = [...pos.flatMap(p => [p.x, p.x + p.w]), ...paths.flatMap(p => p.xs)]
  const minX = Math.min(...xs) - PAD
  const W = Math.max(...xs) - minX + PAD
  return (
    <div style={{ position: 'relative', width: W, height: H + 10, margin: '0 auto' }}>
      <svg width={W} height={H + 10} style={{ position: 'absolute', inset: 0, overflow: 'visible' }} aria-hidden="true">
        <defs>
          {Object.entries(LABEL).map(([k, c]) => (
            <marker key={k || 'plain'} id={`cs-arrow-${k || 'plain'}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 z" fill={c === '#4A5260' ? '#5B6472' : c} />
            </marker>
          ))}
        </defs>
        <g transform={`translate(${-minX} 0)`}>
          {paths.map(p => (
            <g key={p.k}>
              <path d={p.d} fill="none" stroke={p.label ? LABEL[p.label] : '#4A5260'} strokeOpacity={p.label ? 0.75 : 1} strokeWidth="1.6"
                strokeDasharray={p.label === 'back' ? '5 4' : undefined} markerEnd={`url(#cs-arrow-${p.label || 'plain'})`} />
              {p.label && <text x={p.lx} y={p.ly} fill={LABEL[p.label]} fontSize="11" fontFamily="'JetBrains Mono', monospace">{p.label}</text>}
            </g>
          ))}
        </g>
      </svg>
      {blocks.map((b, i) => {
        const p = pos[i]
        const head = b.title.includes('entry') ? '#6CB6FF' : b.title.includes('loop head') ? '#FFA657' : b.title.includes('return') ? '#7EE787' : '#C792EA'
        return (
          <div key={b.id} className="cs-blk mono" style={{ position: 'absolute', left: p.x - minX, top: p.y, width: p.w, minHeight: p.h, boxSizing: 'border-box', background: '#0E1116', borderRadius: 10, padding: 12, border: `1px solid ${head === '#FFA657' ? '#FFA657' : '#2A303A'}`, boxShadow: head === '#FFA657' ? '0 0 24px rgba(255,166,87,0.18)' : 'none', fontSize: 12 }}>
            <div style={{ color: head, fontWeight: 600 }}>{b.title}</div>
            <div style={{ color: '#C5CBD5', marginTop: 8, lineHeight: `${LH}px` }}>
              {b.lines.length ? b.lines.map((l, j) => <div key={j} style={{ whiteSpace: 'pre' }}>{l}</div>) : <div style={{ color: '#5E6674' }}>(empty)</div>}
            </div>
          </div>
        )
      })}
    </div>
  )
}
