export const ORDER = ['python', 'c', 'java', 'js', 'go', 'rust']

export const LANG = {
  python: { label: 'Python 3', short: 'Python', ext: 'py', typing: 'dynamic', run: 'Python 3', monaco: 'python' },
  c: { label: 'C99', short: 'C', ext: 'c', typing: 'static', run: 'C · gcc', monaco: 'c' },
  java: { label: 'Java 21', short: 'Java', ext: 'java', typing: 'static', run: 'Java 21', monaco: 'java' },
  js: { label: 'JavaScript', short: 'JavaScript', ext: 'js', typing: 'dynamic', run: 'Node.js', monaco: 'javascript' },
  go: { label: 'Go', short: 'Go', ext: 'go', typing: 'static', run: 'Go', monaco: 'go' },
  rust: { label: 'Rust', short: 'Rust', ext: 'rs', typing: 'static', run: 'Rust · debug', monaco: 'rust' },
}

export const LC = { python: '#6CB6FF', c: '#89DDFF', java: '#FFA657', js: '#FFCB6B', go: '#7EE787', rust: '#FF8F85' }

export const STAGES = ['Lexer', 'Parser', 'Semantic', 'IR', 'Optimize', 'Codegen']

export const fileOf = lang => `code.${LANG[lang].ext}`

export const hintOf = lang => `${lang === 'python' ? '#' : '//'} Your ${LANG[lang].short} code here. It shifts as you type.\n`

export const blank = (code, lang) => code.split('\n').every(l => !l.trim() || l.trim().startsWith(lang === 'python' ? '#' : '//'))

export const neonGlow = c => `0 0 1px ${c}, 0 0 7px ${c}59, 0 0 16px ${c}26`
