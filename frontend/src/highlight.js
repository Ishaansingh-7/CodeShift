const KW = new Set(['def', 'for', 'in', 'return', 'if', 'else', 'elif', 'while', 'let', 'mut', 'fn', 'func', 'function',
  'public', 'class', 'static', 'void', 'package', 'import', 'var', 'const', 'new', 'as', 'true', 'false', 'True', 'False',
  'not', 'and', 'or', 'pass', 'break', 'continue', 'use', 'pub', 'struct', 'impl', 'match', 'loop', 'range', 'of'])
const TY = new Set(['long', 'int', 'i64', 'int64', 'String', 'boolean', 'bool', 'char', 'string', 'usize', 'str',
  'StringBuilder', 'Vec', 'double', 'float', 'f64', 'u8', 'rune', 'byte'])
const BI = new Set(['print', 'printf', 'System', 'console', 'fmt', 'Println', 'println', 'log', 'Main', 'len', 'strlen',
  'Math', 'Arrays', 'out', 'insert', 'toString', 'swap', 'chars'])
const RE = /(\s+)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(#\w+|<[\w.]+>)|(\d+(?:i64)?)|([A-Za-z_]\w*!?)|([^\sA-Za-z_\d])/g

export function tok(line) {
  const parts = [...line.matchAll(RE)]
  return parts.map((p, i) => {
    let c = 'var(--cDDE1E7)'
    let k = 'OP'
    if (p[1]) k = 'WS'
    else if (p[2]) { c = 'var(--cC3E88D)'; k = 'STRING' }
    else if (p[3]) { c = 'var(--c89DDFF)'; k = 'PRE' }
    else if (p[4]) { c = 'var(--cF78C6C)'; k = 'NUMBER' }
    else if (p[5]) {
      const w = p[5]
      const next = parts.slice(i + 1).find(q => !q[1])
      if (KW.has(w)) { c = 'var(--cC792EA)'; k = 'KEYWORD' }
      else if (TY.has(w)) { c = 'var(--c7FDBCA)'; k = 'TYPE' }
      else if (BI.has(w) || w.endsWith('!')) { c = 'var(--cFFCB6B)'; k = 'BUILTIN' }
      else if (next && next[0] === '(') { c = 'var(--c82AAFF)'; k = 'NAME' }
      else k = 'NAME'
    } else c = 'var(--c8E97A6)'
    return { t: p[0], c, k }
  })
}

const KIND = { KEYWORD: 'var(--cC792EA)', TYPE: 'var(--c7FDBCA)', BUILTIN: 'var(--cFFCB6B)', STRING: 'var(--cC3E88D)', CHAR: 'var(--cC3E88D)',
  NUMBER: 'var(--cF78C6C)', PRE: 'var(--c89DDFF)', OP: 'var(--c8E97A6)', PUNCT: 'var(--c8E97A6)', NAME: 'var(--cDDE1E7)' }

export const tokenColor = kind => KIND[kind] || 'var(--c7B8394)'
