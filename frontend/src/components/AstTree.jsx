import { useMemo, useState } from 'react'

const AW = 156
const AH = 52
const AGX = 12
const ALV = 88
const CAT = {
  Module: ['#6CB6FF', 'Module'], FunctionDef: ['#C792EA', 'Function'], For: ['#FFA657', 'Control flow'],
  While: ['#FFA657', 'Control flow'], If: ['#FFA657', 'Control flow'], Else: ['#FFA657', 'Control flow'],
  Assign: ['#7EE787', 'Statement'], AugAssign: ['#7EE787', 'Statement'], TupleAssign: ['#7EE787', 'Statement'],
  Swap: ['#7EE787', 'Statement'], Return: ['#FF8F85', 'Return'], Call: ['#FFCB6B', 'Call'],
}

function flatten(root) {
  const list = []
  const visit = (n, depth, parent) => {
    const node = { id: list.length, depth, type: n.type, detail: n.detail, parent, kids: [] }
    list.push(node)
    if (parent) parent.kids.push(node)
    n.children.forEach(c => visit(c, depth + 1, node))
  }
  visit(root, 0, null)
  let leaf = 0
  let deep = 0
  const place = n => {
    if (!n.kids.length) { n.x = leaf * (AW + AGX); leaf++ }
    else { n.kids.forEach(place); n.x = (n.kids[0].x + n.kids[n.kids.length - 1].x) / 2 }
    n.y = n.depth * ALV
    deep = Math.max(deep, n.depth)
  }
  place(list[0])
  return { list, W: Math.max(AW, leaf * (AW + AGX) - AGX), H: deep * ALV + AH }
}

export default function AstTree({ ast, file }) {
  const { list, W, H } = useMemo(() => flatten(ast), [ast])
  const [ah, setAh] = useState(-1)
  const path = new Set()
  for (let n = list[ah]; n; n = n.parent) path.add(n.id)
  const hover = list[ah]
  const trim = t => t.length > 20 ? t.slice(0, 19) + '…' : t
  const legend = [...new Map(list.filter(n => CAT[n.type]).map(n => [CAT[n.type][1], CAT[n.type][0]]))]
  return (
    <>
      <div className="cs-chips" onMouseLeave={() => setAh(-1)} style={{ overflowX: 'auto', padding: '24px 18px 20px' }}>
        <div style={{ position: 'relative', margin: '0 auto', width: W, height: H }}>
          {list.filter(n => n.parent).map(n => {
            const x1 = n.parent.x + AW / 2, y1 = n.parent.y + AH, x2 = n.x + AW / 2, y2 = n.y
            const on = path.has(n.id)
            const h = on ? 2 : 1.5
            return <div key={'e' + n.id} className="ast-edge" aria-hidden="true" style={{ position: 'absolute', left: x1, top: y1 - h / 2, width: Math.hypot(x2 - x1, y2 - y1), height: h, borderRadius: 2, background: on ? '#FFA657' : '#39404C', transformOrigin: '0 50%', transform: `rotate(${Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI}deg)`, animationDelay: `${n.depth * 110 - 50}ms` }} />
          })}
          {list.map(n => {
            const c = (CAT[n.type] || ['#DDE1E7'])[0]
            const on = path.has(n.id)
            const me = n.id === ah
            const detail = n.depth === 0 ? file : n.detail
            return (
              <div key={n.id} className="ast-node" title={`${n.type} ${detail}`} onMouseEnter={() => setAh(n.id)}
                style={{ position: 'absolute', left: n.x, top: n.y, width: AW, height: AH, boxSizing: 'border-box', padding: '7px 10px', borderRadius: 10, background: me ? 'rgba(255,166,87,0.12)' : '#161A21', border: `1px solid ${on ? '#FFA657' : '#2A303A'}`, boxShadow: me ? '0 0 0 3px rgba(255,166,87,0.18), 0 10px 26px rgba(0,0,0,0.35)' : on ? '0 0 0 2px rgba(255,166,87,0.10)' : '0 6px 18px rgba(0,0,0,0.25)', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 3, animationDelay: `${n.depth * 110 + Math.min(n.id * 12, 120)}ms` }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 600, letterSpacing: '0.03em', color: c }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', flex: 'none', background: c }} />{n.type}
                </span>
                <span className="mono" style={{ fontSize: 11.5, color: '#DDE1E7', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{trim(detail)}</span>
              </div>
            )
          })}
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', padding: '12px 16px', borderTop: '1px solid #1F242D' }}>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          {legend.map(([t, c]) => <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#A3ABB9' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: c }} />{t}</span>)}
        </div>
        <span className="mono" style={{ fontSize: 11.5, color: hover ? '#FFA657' : '#7B8394' }}>
          {hover ? `depth ${hover.depth} · ${hover.kids.length} ${hover.kids.length === 1 ? 'child' : 'children'} · path from Module highlighted` : 'Hover a node to trace its path to the root'}
        </span>
      </div>
    </>
  )
}
