/**
 * utils/formatters.js — Formatteurs de données pour l'UI
 */

export const fmt = {
  /** Prix avec 2 décimales et symbole monnaie */
  price: (val, currency = '€') => {
    if (val == null) return '—'
    return `${Number(val).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${currency}`
  },

  /** Variation en % avec signe + ou - */
  pct: (val) => {
    if (val == null) return '—'
    const n = Number(val)
    const sign = n >= 0 ? '+' : ''
    return `${sign}${n.toFixed(2)}%`
  },

  /** Nombre entier avec séparateur de milliers */
  volume: (val) => {
    if (val == null) return '—'
    const n = Number(val)
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
    return n.toString()
  },

  /** RSI arrondi à 1 décimale */
  rsi: (val) => {
    if (val == null) return '—'
    return Number(val).toFixed(1)
  },

  /** Score sur 100 */
  score: (val) => {
    if (val == null) return '—'
    return `${Math.round(val)}`
  },

  /** Heure locale HH:MM:SS */
  time: (iso) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  },

  /** Date courte */
  date: (iso) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
  },
}

/** Couleur CSS selon la variation (positif = vert, négatif = rouge) */
export function variationColor(val) {
  if (val == null) return 'text-text-muted'
  return Number(val) >= 0 ? 'text-gain' : 'text-loss'
}

/** Classe CSS du badge selon le signal */
export function signalBadgeClass(signal) {
  const map = {
    STRONG_BUY:   'badge-strong-buy',
    BUY:          'badge-buy',
    NEUTRAL:      'badge-neutral',
    AVOID:        'badge-avoid',
    STRONG_AVOID: 'badge-strong-avoid',
  }
  return map[signal] || 'badge-neutral'
}

/** Label français du signal */
export function signalLabel(signal) {
  const map = {
    STRONG_BUY:   '⬆ FORT ACHAT',
    BUY:          '↑ ACHAT',
    NEUTRAL:      '→ NEUTRE',
    AVOID:        '↓ ÉVITER',
    STRONG_AVOID: '⬇ FORT ÉVITER',
  }
  return map[signal] || signal
}

/** Couleur du score (0-100) */
export function scoreColor(score) {
  if (score >= 70) return 'text-score-high'
  if (score >= 45) return 'text-score-medium'
  return 'text-score-low'
}

/** Couleur de fond de la barre de score */
export function scoreBarColor(score) {
  if (score >= 70) return 'bg-signal-buy'
  if (score >= 45) return 'bg-score-medium'
  return 'bg-signal-avoid'
}
