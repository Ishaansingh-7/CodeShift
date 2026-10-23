import { useEffect, useRef } from 'react'
import { LANG, LC } from '../lang.js'

const rnd = (a, b) => a + Math.random() * (b - a)
const sign = () => (Math.random() < 0.5 ? -1 : 1)
const band = () => {
  const top = rnd(4, 72)
  return `inset(${top.toFixed(0)}% 0 ${Math.max(0, 100 - top - rnd(10, 24)).toFixed(0)}% 0)`
}
const hold = (frames, duration, delay = 0) => node => node.animate(
  frames.flatMap((f, i) => [{ ...f, offset: i / frames.length }, { ...f, offset: (i + 1) / frames.length }]), { duration, delay })

function burst(word) {
  const d = rnd(150, 300), dx = rnd(2, 3) * sign()
  const [s1, s2, a, b] = ['.gl-s1', '.gl-s2', '.gl-a', '.gl-b'].map(c => word.querySelector(c))
  const split = x => [{ opacity: 0.85, transform: `translateX(${x}px)`, clipPath: band() }, { opacity: 0.85, transform: `translateX(${-x / 2}px)`, clipPath: band() }]
  hold(split(dx), d)(a)
  hold(split(-dx), d)(b)
  const n = Math.random() < 0.5 ? 1 : 2
  ;[s1, s2].slice(0, n).forEach((s, i) => hold([{ opacity: 1, transform: `translateX(${rnd(3, 6) * sign()}px)`, clipPath: band() }], d / n, (d / n) * i)(s))
}

function Word({ lang, wref }) {
  const t = LANG[lang].short
  const layer = (cls, color) => <span className={cls} aria-hidden="true" style={{ gridArea: '1 / 1', color }}>{t}</span>
  return (
    <div ref={wref} className="mono" style={{ display: 'grid', fontSize: 'clamp(28px, 2.8vw, 36px)', fontWeight: 800 }}>
      <span className="gl-base" style={{ gridArea: '1 / 1', color: LC[lang] }}>{t}</span>
      {layer('gl-s1', LC[lang])}
      {layer('gl-s2', LC[lang])}
      {layer('gl-a', 'var(--c89DDFF)')}
      {layer('gl-b', 'var(--cFF8F85)')}
    </div>
  )
}

export default function GlitchTitle({ src, tgt, srcFile, tgtFile }) {
  const wa = useRef(null), wb = useRef(null)

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
    let timer
    const next = () => {
      timer = setTimeout(() => {
        if (!reduced.matches && !document.hidden) {
          const p = Math.random()
          for (const r of p < 0.3 ? [wa, wb] : [p < 0.65 ? wa : wb]) if (r.current) burst(r.current)
        }
        next()
      }, rnd(2500, 5000))
    }
    next()
    return () => clearTimeout(timer)
  }, [])

  return (
    <div role="img" aria-label={`From ${LANG[src].short} to ${LANG[tgt].short}`} className="cs-board" style={{ position: 'relative', boxSizing: 'border-box', width: '100%', maxWidth: 560, minHeight: 100, flex: '1 0 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'clamp(14px, 2.6vw, 32px)', padding: 16, borderRadius: 18, background: 'var(--c07080B)', border: '1px solid var(--c1B1F27)', overflow: 'hidden', boxShadow: '0 18px 40px color-mix(in srgb, var(--c000000) 35%, transparent)' }}>
      <div aria-hidden="true" className="gl-scan" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'repeating-linear-gradient(to bottom, color-mix(in srgb, var(--cFFFFFF) 3%, transparent) 0 1px, transparent 1px 4px)' }} />
      <div className="cs-board-side" style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <Word key={'a' + src} lang={src} wref={wa} />
        <span className="mono" style={{ fontSize: 10, letterSpacing: '0.2em', color: 'var(--c5E6674)' }}>FROM · {srcFile}</span>
      </div>
      <span aria-hidden="true" className="mono cs-board-arrow" style={{ position: 'relative', fontSize: 24, fontWeight: 700, color: 'var(--cC792EA)' }}>⇢</span>
      <div className="cs-board-side" style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <Word key={'b' + tgt} lang={tgt} wref={wb} />
        <span className="mono" style={{ fontSize: 10, letterSpacing: '0.2em', color: 'var(--c5E6674)' }}>TO · {tgtFile}</span>
      </div>
    </div>
  )
}
