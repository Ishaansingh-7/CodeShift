import { useEffect, useRef } from 'react'
import { LANG, LC, ORDER } from '../lang.js'

const IR = '199,146,234'
const STILL = [{ from: 0, to: 3, t: -600, d: 2000 }]

const radii = (w, h) => [w / 2 - 64, h / 2 - 30]

function pos(i, t, w, h) {
  const a = t * 0.00012 + i * Math.PI / 3, [rx, ry] = radii(w, h)
  return [w / 2 + Math.cos(a) * rx, h / 2 + Math.sin(a) * ry]
}

function bez(a, b, c, u) {
  const v = 1 - u
  return [v * v * a[0] + 2 * v * u * b[0] + u * u * c[0], v * v * a[1] + 2 * v * u * b[1] + u * u * c[1]]
}

function draw(x, w, h, t, packets) {
  const cx = w / 2, cy = h / 2, [rx, ry] = radii(w, h)
  x.clearRect(0, 0, w, h)
  x.lineWidth = 1
  x.strokeStyle = `rgba(${IR},0.10)`
  x.beginPath(); x.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2); x.stroke()
  x.strokeStyle = `rgba(${IR},0.06)`
  x.beginPath(); x.ellipse(cx, cy, rx * 0.55, ry * 0.55, 0, 0, Math.PI * 2); x.stroke()
  for (const p of packets) {
    const a = pos(p.from, t, w, h), b = pos(p.to, t, w, h), u = (t - p.t) / p.d
    for (let k = 0; k < 10; k++) {
      const uu = u - k * 0.018
      if (uu < 0 || uu > 1) continue
      const pt = uu < 0.5 ? bez(a, [(a[0] + cx) / 2, cy - 40], [cx, cy], uu * 2) : bez([cx, cy], [(b[0] + cx) / 2, cy + 40], b, uu * 2 - 1)
      x.globalAlpha = (1 - k / 10) * 0.9
      x.fillStyle = LC[ORDER[uu < 0.5 ? p.from : p.to]]
      x.beginPath(); x.arc(pt[0], pt[1], 3.2 - k * 0.25, 0, Math.PI * 2); x.fill()
    }
  }
  x.globalAlpha = 1
  const pulse = 0.5 + 0.5 * Math.sin(t * 0.003)
  const glow = x.createRadialGradient(cx, cy, 0, cx, cy, 70)
  glow.addColorStop(0, `rgba(${IR},${0.35 + pulse * 0.2})`)
  glow.addColorStop(1, `rgba(${IR},0)`)
  x.fillStyle = glow
  x.beginPath(); x.arc(cx, cy, 70, 0, Math.PI * 2); x.fill()
  x.fillStyle = '#16121C'; x.strokeStyle = '#C792EA'; x.lineWidth = 1.5
  x.beginPath(); x.arc(cx, cy, 30, 0, Math.PI * 2); x.fill(); x.stroke()
  x.fillStyle = '#E9D9F5'; x.font = '600 13px "JetBrains Mono", monospace'; x.textAlign = 'center'; x.textBaseline = 'middle'
  x.fillText('IR', cx, cy)
  x.font = '500 12px "JetBrains Mono", monospace'
  ORDER.forEach((l, i) => {
    const [px, py] = pos(i, t, w, h)
    const hot = packets.some(q => (q.to === i && (t - q.t) / q.d > 0.92) || (q.from === i && (t - q.t) / q.d < 0.08))
    const name = LANG[l].short, bw = x.measureText(name).width + 26
    x.fillStyle = '#0E1116'; x.strokeStyle = hot ? LC[l] : '#2A303A'; x.lineWidth = hot ? 2 : 1
    x.beginPath()
    if (x.roundRect) x.roundRect(px - bw / 2, py - 15, bw, 30, 10)
    else x.rect(px - bw / 2, py - 15, bw, 30)
    x.fill(); x.stroke()
    if (hot) { x.shadowColor = LC[l]; x.shadowBlur = 12; x.stroke(); x.shadowBlur = 0 }
    x.fillStyle = LC[l]; x.fillText(name, px, py + 1)
  })
}

export default function HeroOrbit() {
  const ref = useRef(null)

  useEffect(() => {
    const cv = ref.current
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
    let g = { w: 0 }, raf = 0, prev = 0, t = 0, last = 0, packets = [], alive = true

    const fit = () => {
      const r = cv.getBoundingClientRect(), d = Math.min(window.devicePixelRatio || 1, 2)
      cv.width = Math.max(1, Math.round(r.width * d))
      cv.height = Math.max(1, Math.round(r.height * d))
      const x = cv.getContext('2d')
      x.setTransform(d, 0, 0, d, 0, 0)
      g = { x, w: r.width, h: r.height }
    }
    const paint = () => { if (g.w) draw(g.x, g.w, g.h, t, packets) }
    const frame = now => {
      t += Math.min(now - prev, 50)
      prev = now
      if (t - last > 650) {
        last = t
        const a = (Math.random() * 6) | 0
        packets.push({ from: a, to: (a + 1 + ((Math.random() * 5) | 0)) % 6, t, d: 2200 })
      }
      packets = packets.filter(p => t - p.t < p.d)
      paint()
      raf = requestAnimationFrame(frame)
    }
    const sync = () => {
      cancelAnimationFrame(raf)
      raf = 0
      if (!alive) return
      if (reduced.matches) {
        t = 0
        packets = STILL
        paint()
      } else if (!document.hidden && g.w) {
        if (packets === STILL) packets = []
        prev = performance.now()
        raf = requestAnimationFrame(frame)
      }
    }

    const ro = new ResizeObserver(() => { fit(); sync() })
    ro.observe(cv)
    reduced.addEventListener('change', sync)
    document.addEventListener('visibilitychange', sync)
    document.fonts?.ready.then(() => { if (raf === 0) sync() })
    return () => {
      alive = false
      cancelAnimationFrame(raf)
      ro.disconnect()
      reduced.removeEventListener('change', sync)
      document.removeEventListener('visibilitychange', sync)
    }
  }, [])

  return <canvas ref={ref} className="cs-orbit" aria-hidden="true" style={{ width: 340, maxWidth: '100%', aspectRatio: '34 / 23' }} />
}
