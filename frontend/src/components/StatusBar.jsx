import { LANG, STAGES } from '../lang.js'

function linesIn(rows, g) {
  const nums = rows.flatMap((r, i) => r.group === g ? [i + 1] : [])
  if (!nums.length) return ''
  const parts = []
  let start = nums[0]
  let prev = nums[0]
  for (let i = 1; i <= nums.length; i++) {
    if (i < nums.length && nums[i] === prev + 1) { prev = nums[i]; continue }
    parts.push(start === prev ? String(start) : `${start}–${prev}`)
    if (i < nums.length) { start = nums[i]; prev = nums[i] }
  }
  return 'L' + parts.join(', ')
}

export default function StatusBar({ ctx }) {
  const { busy, phase, error, blocked, empty, result, cfg, hg, health, groupName, srcFile, tgtFile } = ctx
  let text, color, pulse = false
  if (health.state === 'offline') { text = `API offline · retrying`; color = '#FF8F85'; pulse = true }
  else if (busy) { text = `Shifting · ${STAGES[Math.min(phase, 5)]}`; color = '#FFA657'; pulse = true }
  else if (empty) { text = 'Waiting for code · write or paste a program'; color = '#7B8394' }
  else if (blocked) { text = `Not supported in ${LANG[cfg.tgt].short} · ${error.message.replace(/^Unsupported: /, '')}`; color = '#FFCB6B' }
  else if (error) { text = `Error · ${error.message}`; color = '#FF8F85' }
  else if (result) { text = 'Shifted · 0 errors'; color = '#7EE787' }
  else { text = 'Connecting to the compiler'; color = '#FFA657'; pulse = true }
  let map = 'Hover any line to see where it maps'
  if (hg >= 0 && result && !error) {
    map = `${groupName} · ${srcFile} ${linesIn(result.srcLines, hg) || 'none'}  ↔  ${tgtFile} ${linesIn(result.tgtLines, hg) || 'none'}`
  }
  const types = result && !error && !empty ? (result.types.length ? 'types: ' + result.types.join(' · ') : 'types: dynamic') : ''
  return (
    <div className="mono" role="status" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginTop: 12, padding: '10px 16px', background: 'rgba(14,17,22,0.9)', border: `1px solid ${blocked ? 'rgba(255,203,107,0.3)' : error ? 'rgba(255,143,133,0.35)' : '#1B1F27'}`, borderRadius: 10, fontSize: 12, color: '#A3ABB9' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap', minWidth: 0 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: blocked ? '#FFCB6B' : error ? '#FF8F85' : undefined }}>
          <span className={pulse ? 'cs-pulse' : ''} style={{ width: 7, height: 7, borderRadius: '50%', background: color, flex: 'none' }} />{text}
        </span>
        {types && <span>{types}</span>}
        {result && !error && !empty && <span>{cfg.optimize ? 'passes: fold · cse · copy-prop · dce' : 'passes: off'}</span>}
      </div>
      <span style={{ color: hg >= 0 ? '#E6E9EF' : '#7B8394' }}>{map}</span>
    </div>
  )
}
