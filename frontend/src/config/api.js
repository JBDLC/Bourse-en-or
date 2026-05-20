/**
 * URL API — VITE_API_URL est figée au build Render.
 * Si absente, détection automatique pour les apps *.onrender.com
 */
const DEFAULT_RENDER_BACKEND = 'https://pea-trading-backend.onrender.com'

function stripSlash(url) {
  return (url || '').replace(/\/$/, '')
}

export function getApiBase() {
  const fromEnv = import.meta.env.VITE_API_URL
  if (fromEnv) return stripSlash(fromEnv)

  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host.endsWith('.onrender.com')) {
      // ex: bourse-en-or-frontend → bourse-en-or-backend
      if (host.includes('frontend')) {
        return `https://${host.replace('frontend', 'backend')}`
      }
      return DEFAULT_RENDER_BACKEND
    }
  }

  return 'http://localhost:8000'
}

export function getWsUrl() {
  const fromEnv = import.meta.env.VITE_WS_URL
  if (fromEnv) return fromEnv

  const api = getApiBase()
  return api.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:') + '/ws'
}

export const API_BASE = getApiBase()
