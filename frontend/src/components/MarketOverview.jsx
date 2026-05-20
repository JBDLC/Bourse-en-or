/**
 * components/MarketOverview.jsx
 * Barre des indices de référence (CAC40, Euro Stoxx, DAX...)
 */
import { useEffect, useState } from 'react'
import { fmt, variationColor } from '../utils/formatters'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function MarketOverview() {
  const [indices, setIndices] = useState([])
  const [loading, setLoading] = useState(true)
  const [apiError, setApiError] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        setApiError(false)
        const res = await fetch(`${API_BASE}/api/indices`)
        if (res.ok) {
          const data = await res.json()
          setIndices(data.indices || [])
        } else {
          setApiError(true)
        }
      } catch (e) {
        console.error('Erreur chargement indices:', e)
        setApiError(true)
      } finally {
        setLoading(false)
      }
    }

    load()
    const interval = setInterval(load, 60_000) // refresh toutes les minutes
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="flex gap-4 px-4 py-2 border-b border-bg-border overflow-x-auto">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex gap-2 items-center min-w-max animate-pulse">
            <div className="h-3 w-16 bg-bg-hover rounded" />
            <div className="h-3 w-12 bg-bg-hover rounded" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex gap-6 px-4 py-2 border-b border-bg-border overflow-x-auto bg-bg-secondary/50 scrollbar-hide">
      {indices.map((idx) => (
        <div key={idx.ticker} className="flex items-center gap-2 min-w-max">
          <span className="text-xs text-text-secondary font-medium">{idx.name}</span>
          <span className="num text-xs text-text-primary font-semibold">
            {fmt.price(idx.price, '')}
          </span>
          <span className={`num text-xs font-medium ${variationColor(idx.change_pct)}`}>
            {fmt.pct(idx.change_pct)}
          </span>
        </div>
      ))}

      {indices.length === 0 && (
        <span className="text-xs text-text-muted">
          {apiError
            ? 'Indices indisponibles (vérifiez CORS / URL backend)'
            : 'Indices non disponibles (collecte en cours ou marché fermé)'}
        </span>
      )}
    </div>
  )
}
