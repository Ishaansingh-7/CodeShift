import { useEffect, useRef, useState } from 'react'
import * as api from '../api.js'
import { LANG, LC, ORDER, blank } from '../lang.js'
import { lineStats } from '../lines.js'

const KINDS = [['logic', 'var(--cFFA657)', 'logic'], ['setup', 'var(--c6CB6FF)', 'setup'], ['brace', 'var(--c3A404C)', 'braces'], ['blank', 'var(--c1F242D)', 'blank']]
const MUTED = 'var(--c7B8394)'
const fx = x => x.toFixed(1)
const name = l => <span style={{ color: LC[l] }}>{LANG[l].short}</span>
const linesOf = code => code.replace(/\n+$/, '').split('\n')

function words(st, S, T) {
  if (!st[T]) return [<>{name(S)}: {st[S].total} lines</>, `${LANG[T].short} can't take this program yet, so it has no bar.`]
  const [big, small] = st[T].total >= st[S].total ? [T, S] : [S, T]
  const r = st[big].total / st[small].total
  if (fx(r) === '1.0') {
    const over = l => st[l].setup + st[l].brace
    return [<>{name(T)} is about as long as {name(S)}</>, `Logic: ${st[S].logic} vs ${st[T].logic} lines. Setup and braces: ${over(S)} vs ${over(T)}.`]
  }
  const lr = st[small].logic ? st[big].logic / st[small].logic : 1
  const sub = lr < 0.95 ? 'with even less logic. The rest is setup and braces.'
    : fx(lr) === '1.0' ? 'with the same amount of logic. The rest is setup and braces.'
    : lr < r - 0.1 ? `but only ${fx(lr)}× the logic. The rest is setup and braces.`
    : `Logic grows ${fx(lr)}× too, not just setup and braces.`
  return [<>{name(big)} is {fx(r)}× as long as {name(small)}</>, sub]
}

export default function HeroLines({ shot }) {
  const cache = useRef(new Map())
  const latest = useRef(shot)
  latest.current = shot
  const [data, setData] = useState(null)
  const [stale, setStale] = useState(false)
  const key = shot && !blank(shot.code, shot.src) ? [shot.src, shot.optimize, shot.code].join('\u0000') : null

  useEffect(() => {
    if (!key) return
    const hit = cache.current.get(key)
    if (hit) {
      setData({ ...hit, tgt: latest.current.tgt })
      setStale(false)
      return
    }
    let alive = true
    const { src, code, optimize } = latest.current
    const others = ORDER.filter(l => l !== src)
    Promise.all(others.map(l => api.translate(src, l, code, optimize).catch(() => null))).then(res => {
      if (!alive) return
      if (res.every(r => !r) || res.some(r => r?.errors[0]?.side === 'source')) return setStale(true)
      const ok = res.find(r => r && !r.errors.length)
      const stats = { [src]: lineStats(src, ok ? ok.srcLines.map(x => x.text) : linesOf(code)) }
      others.forEach((l, i) => { stats[l] = res[i] && !res[i].errors.length ? lineStats(l, res[i].tgtLines.map(x => x.text)) : null })
      const next = { key, src, stats }
      cache.current.set(key, next)
      if (cache.current.size > 8) cache.current.delete(cache.current.keys().next().value)
      setData({ ...next, tgt: latest.current.tgt })
      setStale(false)
    })
    return () => { alive = false }
  }, [key])

  const st = key ? data?.stats : null
  const S = data?.src
  const T = data?.key === key ? shot.tgt : data?.tgt
  let [head, sub] = !key ? ['Same program, six languages', 'Write or pick a program to see how long it is in each.']
    : !st ? ['Measuring…', 'Translating into all six languages.']
    : words(st, S, T)
  if (st && stale) sub = 'Showing the last version that compiled.'
  const langs = st ? [...ORDER].sort((a, b) => (st[a]?.total ?? Infinity) - (st[b]?.total ?? Infinity)) : ORDER
  const max = st ? Math.max(1, ...ORDER.map(l => st[l]?.total ?? 0)) : 1

  return (
    <div className="cs-orbit" style={{ width: '100%', maxWidth: 520, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <span style={{ fontSize: 19, fontWeight: 650, letterSpacing: '-0.02em', lineHeight: 1.2, color: 'var(--cE6E9EF)' }}>{head}</span>
        <span style={{ fontSize: 12, color: MUTED }}>{sub}</span>
      </div>
      <div className={'mono' + (st && stale ? ' cs-stale' : '')} role="list" aria-label="Lines of code in each language" style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {langs.map(l => {
          const s = st?.[l]
          const pair = st && (l === S || l === T)
          const label = s ? `${LANG[l].short}: ${s.total} lines (${s.logic} logic, ${s.setup} setup, ${s.brace} braces, ${s.blank} blank)` : `${LANG[l].short}: ${st ? 'not supported' : 'no data yet'}`
          return (
            <div key={l} role="listitem" title={label} aria-label={label}
              style={{ height: 24, boxSizing: 'border-box', padding: '0 8px', borderRadius: 7, display: 'flex', alignItems: 'center', gap: 8, border: `1.5px solid ${pair ? LC[l] : 'transparent'}`, background: pair ? 'var(--c11141A)' : 'transparent' }}>
              <span style={{ width: 80, flex: 'none', fontSize: 11, color: pair ? LC[l] : MUTED, fontWeight: pair ? 600 : 400 }}>{LANG[l].short}</span>
              {s && (
                <>
                  <span aria-hidden="true" style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 2 }}>
                    {KINDS.map(([k, c]) => s[k] > 0 && <span key={k} style={{ flex: 'none', width: `max(2px, calc((100% - 44px) * ${s[k] / max}))`, height: 10, borderRadius: 2, background: c }} />)}
                    <span style={{ marginLeft: 6, fontSize: 10.5, color: MUTED }}>{s.total}</span>
                  </span>
                </>
              )}
              {st && !s && <span style={{ fontSize: 10.5, color: MUTED }}>not supported</span>}
              <span aria-hidden="true" style={{ marginLeft: 'auto', width: 44, flex: 'none', textAlign: 'right', fontFamily: "'Geist', system-ui, sans-serif", fontSize: 14, fontWeight: 650, letterSpacing: '-0.01em', color: s ? 'var(--cE6E9EF)' : MUTED }}>
                {s ? `×${fx(s.total / st[S].total)}` : '—'}
              </span>
            </div>
          )
        })}
      </div>
      <div className="mono" aria-hidden="true" style={{ display: 'flex', gap: 12, paddingLeft: 9, fontSize: 10.5, color: MUTED }}>
        {KINDS.map(([k, c, word]) => (
          <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: c }} />{word}
          </span>
        ))}
      </div>
    </div>
  )
}
