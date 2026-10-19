import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as api from './api.js'
import { LANG, blank, fileOf, hintOf } from './lang.js'
import { tok } from './highlight.js'
import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import LangPicker from './components/LangPicker.jsx'
import Toolbar from './components/Toolbar.jsx'
import StageTrack from './components/StageTrack.jsx'
import Panes from './components/Panes.jsx'
import HistoryList from './components/HistoryList.jsx'
import StatusBar from './components/StatusBar.jsx'
import ResultTabs from './components/ResultTabs.jsx'
import PipelineView from './components/PipelineView.jsx'
import SamplesPage from './components/SamplesPage.jsx'
import Footer from './components/Footer.jsx'

const STEP = 170
const HISTORY = 'codeshift.history'
const CUSTOM = 'codeshift.custom'
const VIEWS = { '#/samples': 'samples', '#/pipeline': 'pipe' }
const HASH = { samples: '#/samples', pipe: '#/pipeline', play: '#/' }
const viewOf = () => VIEWS[window.location.hash] || 'play'
const reduced = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const sleep = ms => new Promise(r => setTimeout(r, ms))

function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY) || '[]').slice(0, 8) } catch { return [] }
}

function loadCustom() {
  try { return JSON.parse(localStorage.getItem(CUSTOM) || '{}') } catch { return {} }
}

function failed(message) {
  return { output: '', srcLines: [], tgtLines: [], tokens: [], ast: null, symbols: [], ir: [], cfg: { blocks: [], edges: [] },
    types: [], changed: [], approx: [], groups: [], stats: { tokens: 0, irOps: 0, removed: 0, lines: 0 },
    errors: [{ message, line: 0, col: 0, stage: 'network' }] }
}

export default function App() {
  const [view, setViewState] = useState(viewOf)
  const [health, setHealth] = useState({ state: 'connecting', info: null })
  const [catalog, setCatalog] = useState([])
  const [cfg, setCfg] = useState({ src: 'python', tgt: 'c', sample: 'fib', optimize: true })
  const [code, setCode] = useState('')
  const [rt, setRt] = useState(false)
  const [result, setResult] = useState(null)
  const [good, setGood] = useState(null)
  const [busy, setBusy] = useState(false)
  const [phase, setPhase] = useState(7)
  const [rev, setRev] = useState(-1)
  const [diff, setDiff] = useState(null)
  const [ran, setRan] = useState(0)
  const [round, setRound] = useState(null)
  const [hist, setHist] = useState(loadHistory)
  const [hg, setHg] = useState(-1)
  const [fs, setFs] = useState('')
  const [tab, setTab] = useState('run')
  const [stdin, setStdinState] = useState('')
  const stdinRef = useRef('')
  const testSeq = useRef(0)
  const stdinTimer = useRef(null)
  const seq = useRef(0)
  const timers = useRef([])
  const typing = useRef(null)
  const custom = useRef(loadCustom())

  const sample = catalog.find(s => s.id === cfg.sample)

  useEffect(() => {
    const sync = () => { setViewState(viewOf()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])
  const setView = v => { window.location.hash = HASH[v] }

  useEffect(() => {
    let alive = true
    let t
    const load = () => Promise.all([api.health(), api.samples()])
      .then(([info, list]) => {
        if (!alive) return
        setHealth({ state: 'online', info })
        setCatalog(list)
      })
      .catch(() => {
        if (!alive) return
        setHealth({ state: 'offline', info: null })
        t = setTimeout(load, 2000)
      })
    load()
    const poll = setInterval(() => api.health().then(info => alive && setHealth({ state: 'online', info })).catch(() => {}), 15000)
    return () => { alive = false; clearTimeout(t); clearInterval(poll) }
  }, [])

  const clearTimers = () => { timers.current.forEach(clearTimeout); timers.current = [] }

  const record = useCallback((entry) => {
    setHist(h => {
      const next = [entry, ...h.filter(e => !(e.src === entry.src && e.tgt === entry.tgt && e.sample === entry.sample && e.code === entry.code))].slice(0, 8)
      try { localStorage.setItem(HISTORY, JSON.stringify(next)) } catch { }
      return next
    })
  }, [])

  const shift = useCallback(async (p) => {
    const id = ++seq.current
    clearTimers()
    clearTimeout(typing.current)
    if (blank(p.code, p.src)) {
      ++testSeq.current
      setBusy(false); setPhase(7); setRev(-1); setDiff(null); setRan(0); setRound(null); setHg(-1); setResult(null)
      return
    }
    const fast = reduced()
    setBusy(true); setPhase(0); setRev(-1); setDiff(null); setRan(0); setRound(null); setHg(-1)
    if (!fast) for (let k = 1; k <= 5; k++) timers.current.push(setTimeout(() => seq.current === id && setPhase(k), k * STEP))
    const started = performance.now()
    let res
    try { res = await api.translate(p.src, p.tgt, p.code, p.optimize) } catch (e) { res = failed('The API is not reachable. Is the backend running on ' + api.API_URL + '?') }
    if (!fast) await sleep(Math.max(0, 6 * STEP - (performance.now() - started)))
    if (seq.current !== id) return
    clearTimers()
    setBusy(false); setPhase(7); setResult(res)
    if (res.errors.length) return
    setGood({ ...res, src: p.src, tgt: p.tgt, sample: p.sample })
    const total = res.tgtLines.reduce((n, l) => n + tok(l.text).length, 0)
    if (!fast) {
      for (let r = 0; r < total; r += 3) {
        await sleep(16)
        if (seq.current !== id) return
        setRev(r)
      }
    }
    setRev(-1)
    const entry = { src: p.src, tgt: p.tgt, sample: p.sample, code: p.code, t: Date.now(), srcN: res.srcLines.length, tgtN: res.tgtLines.length, match: null }
    record(entry)
    const unchanged = catalog.find(s => s.id === p.sample)?.code[p.src] === p.code
    const test = ++testSeq.current
    const [d, back] = await Promise.all([
      api.difftest(p.src, p.tgt, p.code, unchanged ? p.sample : null, stdinRef.current).catch(() => ({ rows: [], label: '', program: null, errors: [{ message: 'Difftest request failed' }] })),
      p.rt ? api.translate(p.tgt, p.src, res.output, p.optimize).catch(() => null) : Promise.resolve(null),
    ])
    if (seq.current !== id || testSeq.current !== test) return
    setDiff(d)
    if (back) setRound(back.errors.length ? { error: back.errors[0].message } : { same: back.output.trim() === p.code.trim(), lines: back.output.split('\n').length })
    const n = d.rows.length
    const m = d.rows.filter(r => r.match).length
    record({ ...entry, match: n ? `${m}/${n}` : d.program ? (d.program.match ? 'same output' : 'output differs') : null })
    for (let k = 1; k <= n; k++) timers.current.push(setTimeout(() => seq.current === id && setRan(k), fast ? 0 : k * 240))
  }, [catalog, record])

  const retest = useCallback(async (text) => {
    if (!good || busy || !result || result.errors.length || blank(code, cfg.src)) return
    const test = ++testSeq.current
    setDiff(null); setRan(0)
    const unchanged = catalog.find(s => s.id === cfg.sample)?.code[cfg.src] === code
    const d = await api.difftest(cfg.src, cfg.tgt, code, unchanged ? cfg.sample : null, text)
      .catch(() => ({ rows: [], label: '', program: null, errors: [{ message: 'Difftest request failed' }] }))
    if (testSeq.current !== test) return
    setDiff(d)
    setRan(d.rows.length)
  }, [good, busy, result, catalog, cfg, code])

  const setStdin = (text, now = false) => {
    setStdinState(text)
    stdinRef.current = text
    clearTimeout(stdinTimer.current)
    if (!now) stdinTimer.current = setTimeout(() => retest(text), 600)
  }

  const go = useCallback((patch, nextCode) => {
    const next = { ...cfg, ...patch }
    if (patch.sample !== undefined) {
      const s = catalog.find(x => x.id === patch.sample)
      stdinRef.current = s?.stdin || ''
      setStdinState(stdinRef.current)
    }
    const c = nextCode ?? code
    setCfg(next)
    setCode(c)
    shift({ ...next, code: c, rt })
  }, [cfg, code, rt, shift, catalog])

  const sampleCode = (id, lang) => catalog.find(s => s.id === id)?.code[lang] ?? ''
  const customOf = lang => {
    const c = custom.current[lang]
    return c && !blank(c, lang) ? c : hintOf(lang)
  }

  useEffect(() => {
    if (cfg.sample !== null || !catalog.length) return
    custom.current = { ...custom.current, [cfg.src]: code }
    try { localStorage.setItem(CUSTOM, JSON.stringify(custom.current)) } catch { }
  }, [code, cfg.sample, cfg.src])

  useEffect(() => {
    if (!catalog.length || code) return
    const c = sampleCode(cfg.sample, cfg.src)
    stdinRef.current = catalog.find(x => x.id === cfg.sample)?.stdin || ''
    setStdinState(stdinRef.current)
    setCode(c)
    shift({ ...cfg, code: c, rt })
  }, [catalog])

  const pickSrc = l => {
    if (l === cfg.src) return
    if (l === cfg.tgt) return swap()
    go({ src: l }, cfg.sample === null ? customOf(l) : sampleCode(cfg.sample, l))
  }
  const pickTgt = l => {
    if (l === cfg.tgt) return
    if (l === cfg.src) return swap()
    go({ tgt: l })
  }
  const swap = () => {
    const ok = result && !result.errors.length
    go({ src: cfg.tgt, tgt: cfg.src }, cfg.sample !== null ? sampleCode(cfg.sample, cfg.tgt) : ok ? result.output : customOf(cfg.tgt))
  }
  const pickSample = id => go({ sample: id }, sampleCode(id, cfg.src))
  const pickCustom = () => cfg.sample !== null && go({ sample: null }, customOf(cfg.src))
  const openSample = id => { setView('play'); go({ sample: id }, sampleCode(id, cfg.src)) }
  const restore = e => go({ src: e.src, tgt: e.tgt, sample: e.sample && e.code === sampleCode(e.sample, e.src) ? e.sample : null }, e.code)
  const onType = value => {
    const next = cfg.sample !== null && value !== sampleCode(cfg.sample, cfg.src) ? { ...cfg, sample: null } : cfg
    if (next !== cfg) setCfg(next)
    setCode(value)
    clearTimeout(typing.current)
    typing.current = setTimeout(() => shift({ ...next, code: value, rt }), 600)
  }
  const toggleRt = () => { setRt(!rt); if (!rt && result && !result.errors.length) shift({ ...cfg, code, rt: true }) }

  const error = result?.errors[0] || null
  const blocked = error?.side === 'target'
  const empty = !busy && cfg.sample === null && blank(code, cfg.src)
  const shown = error ? good : result
  const stale = !!error
  const srcFile = fileOf(cfg.src)
  const tgtFile = fileOf(cfg.tgt)
  const groupName = hg >= 0 && shown ? shown.groups[hg] : null

  const ctx = { cfg, sample, catalog, code, result, shown, good, error, blocked, empty, stale, busy, phase, rev, diff, ran, round, rt, hg, setHg,
    fs, setFs, tab, setTab, srcFile, tgtFile, health, groupName, hist, stdin, setStdin }

  return (
    <div className="cs-grid cs-root">
      <div className="cs-wrap">
        <Header view={view} setView={setView} />
        {view === 'play' && (
          <>
            <Hero src={cfg.src} tgt={cfg.tgt} srcFile={srcFile} tgtFile={tgtFile}
              picker={<LangPicker src={cfg.src} tgt={cfg.tgt} pickSrc={pickSrc} pickTgt={pickTgt} swap={swap} />}
              actions={<Toolbar optimize={cfg.optimize} toggleOpt={() => go({ optimize: !cfg.optimize })} rt={rt} toggleRt={toggleRt}
                busy={busy} doShift={() => shift({ ...cfg, code, rt })} />} />
            <StageTrack ctx={ctx} />
            {rt && <RoundTrip ctx={ctx} />}
            <Panes ctx={ctx} onType={onType} pickSample={pickSample} pickCustom={pickCustom} pickTgt={pickTgt} />
            <HistoryList hist={hist} cur={{ ...cfg, code }} catalog={catalog} restore={restore}
              clear={() => { setHist([]); try { localStorage.removeItem(HISTORY) } catch { } }} />
            <StatusBar ctx={ctx} />
            <ResultTabs ctx={ctx} rerun={() => shift({ ...cfg, code, rt })} />
          </>
        )}
        {view === 'pipe' && <PipelineView ctx={ctx} toPlay={() => setView('play')} />}
        {view === 'samples' && <SamplesPage catalog={catalog} open={openSample} offline={health.state === 'offline'} />}
        <Footer />
      </div>
    </div>
  )
}

function RoundTrip({ ctx }) {
  const { cfg, diff, round, busy, error, empty } = ctx
  const a = LANG[cfg.src].short
  const b = LANG[cfg.tgt].short
  const m = diff?.rows.filter(r => r.match).length
  const n = diff?.rows.length
  let text = 'Translating back…'
  if (!busy && (error || empty)) text = 'Round-trip runs after a successful shift.'
  else if (!busy && round?.error) text = `Round-trip unavailable: ${round.error}`
  else if (!busy && round) {
    const back = round.same ? `translated back, ${a} is identical to the original.` : `translated back, ${a} differs from the original text (${round.lines} lines).`
    text = (n ? `${b} matches ${a} on ${m} of ${n} inputs; ` : '') + back
  }
  const pill = (t, c, bg) => <span style={{ padding: '4px 9px', borderRadius: 6, background: bg, color: c }}>{t}</span>
  return (
    <div className="cs-up" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap', marginTop: 12, padding: '12px 16px', background: 'rgba(199,146,234,0.07)', border: '1px solid rgba(199,146,234,0.3)', borderRadius: 12 }}>
      <div className="mono" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 12.5 }}>
        {pill(a, '#6CB6FF', 'rgba(108,182,255,0.12)')}<span style={{ color: '#7B8394' }}>→</span>
        {pill(b, '#FFA657', 'rgba(255,166,87,0.12)')}<span style={{ color: '#7B8394' }}>→</span>
        {pill(a, '#6CB6FF', 'rgba(108,182,255,0.12)')}
      </div>
      <span style={{ color: '#C5CBD5', fontSize: 13.5 }}>{text}</span>
    </div>
  )
}
