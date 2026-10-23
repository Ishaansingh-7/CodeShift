import { useSyncExternalStore } from 'react'

const KEY = 'cs-theme'
const subs = new Set()
const media = window.matchMedia('(prefers-color-scheme: light)')

const saved = () => {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

let current = saved() || (media.matches ? 'light' : 'dark')

const apply = () => {
  document.documentElement.dataset.theme = current
  subs.forEach(f => f())
}

media.addEventListener('change', e => {
  if (!saved()) {
    current = e.matches ? 'light' : 'dark'
    apply()
  }
})

apply()

export const getTheme = () => current

export const setTheme = t => {
  current = t
  try {
    localStorage.setItem(KEY, t)
  } catch {}
  apply()
}

export const useTheme = () => useSyncExternalStore(f => (subs.add(f), () => subs.delete(f)), getTheme)
