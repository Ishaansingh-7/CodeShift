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
    let c = '#DDE1E7'
    let k = 'OP'
    if (p[1]) k = 'WS'
    else if (p[2]) { c = '#C3E88D'; k = 'STRING' }
    else if (p[3]) { c = '#89DDFF'; k = 'PRE' }
    else if (p[4]) { c = '#F78C6C'; k = 'NUMBER' }
    else if (p[5]) {
      const w = p[5]
      const next = parts.slice(i + 1).find(q => !q[1])
      if (KW.has(w)) { c = '#C792EA'; k = 'KEYWORD' }
      else if (TY.has(w)) { c = '#7FDBCA'; k = 'TYPE' }
      else if (BI.has(w) || w.endsWith('!')) { c = '#FFCB6B'; k = 'BUILTIN' }
      else if (next && next[0] === '(') { c = '#82AAFF'; k = 'NAME' }
      else k = 'NAME'
    } else c = '#8E97A6'
    return { t: p[0], c, k }
  })
}

const KIND = { KEYWORD: '#C792EA', TYPE: '#7FDBCA', BUILTIN: '#FFCB6B', STRING: '#C3E88D', CHAR: '#C3E88D',
  NUMBER: '#F78C6C', PRE: '#89DDFF', OP: '#8E97A6', PUNCT: '#8E97A6', NAME: '#DDE1E7' }

export const tokenColor = kind => KIND[kind] || '#7B8394'
