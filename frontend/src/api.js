export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function call(path, body) {
  const r = await fetch(API_URL + path, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${path} ${r.status}`)
  return r.json()
}

export const health = () => call('/health')
export const samples = () => call('/samples')
export const translate = (src, tgt, code, optimize) => call('/translate', { src, tgt, code, optimize })
export const run = (lang, code, inputs) => call('/run', { lang, code, inputs })
export const difftest = (src, tgt, code, sample, stdin) => call('/difftest', { src, tgt, code, sample, stdin })
