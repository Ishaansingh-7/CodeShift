const SETUP = {
  python: /^(import\s|from\s+\S+\s+import\s)/,
  c: /^(#|int\s+main\s*\()/,
  java: /^(import\s|package\s|(public\s+)?(final\s+)?class\s|public\s+static\s+void\s+main\s*\()/,
  js: /^(['"]use strict['"]|import\s|(const|let|var)\s+\w+\s*=\s*require\()/,
  go: /^(package\s|import\b|func\s+main\s*\()/,
  rust: /^(use\s|fn\s+main\s*\()/,
}
const PUNCT = /^[{}()[\];,]+$/
const comment = (lang, t) => (lang === 'python' ? t.startsWith('#') : /^(\/\/|\/\*|\*\/|\*\s)/.test(t))

export function lineStats(lang, lines) {
  const s = { logic: 0, setup: 0, brace: 0, blank: 0, total: lines.length }
  let imports = false
  for (const raw of lines) {
    const t = raw.trim()
    if (imports) {
      s.setup++
      if (t === ')') imports = false
    } else if (!t || comment(lang, t)) s.blank++
    else if (PUNCT.test(t)) s.brace++
    else if (SETUP[lang].test(t)) {
      s.setup++
      if (lang === 'go' && /^import\s*\($/.test(t)) imports = true
    } else s.logic++
  }
  return s
}
