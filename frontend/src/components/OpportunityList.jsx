/**
 * components/OpportunityList.jsx
 * Liste des meilleures opportunités d'investissement scorées par l'IA
 */
import { useEffect, useState, useRef } from 'react'
import { fmt, variationColor, scoreColor, scoreBarColor } from '../utils/formatters'
import SignalBadge from './SignalBadge'
import { Sparkles, TrendingUp, AlertTriangle } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function OpportunityList({ wsQuotes, onSelectTicker }) {
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [filter, setFilter] = useState('ALL') // ALL | BUY | NEUTRAL
  const prevPrices = useRef({})

  // Fetch initial + refresh toutes les 2 minutes
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/recommendations?limit=30`)
        if (res.ok) {
          const data = await res.json()
          setRecommendations(data.recommendations || [])
          setLastUpdate(new Date())
        }
      } catch (e) {
        console.error('Erreur recommandations:', e)
      } finally {
        setLoading(false)
      }
    }

    load()
    const interval = setInterval(load, 120_000)
    return () => clearInterval(interval)
  }, [])

  // Merger les prix temps réel depuis WebSocket
  const merged = recommendations.map(rec => {
    const ws = wsQuotes[rec.ticker]
    if (ws) {
      return {
        ...rec,
        price: ws.price ?? rec.price,
        change_pct: ws.change_pct ?? rec.change_pct,
        signal: ws.signal ?? rec.signal,
        score: ws.score ?? rec.score,
      }
    }
    return rec
  })

  const filtered = filter === 'ALL'
    ? merged
    : filter === 'BUY'
      ? merged.filter(r => ['STRONG_BUY', 'BUY'].includes(r.signal))
      : merged.filter(r => r.signal === 'NEUTRAL')

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="p-3 border-b border-bg-border animate-pulse">
            <div className="flex gap-2 mb-2">
              <div className="h-4 w-20 bg-bg-hover rounded" />
              <div className="h-4 w-16 bg-bg-hover rounded" />
            </div>
            <div className="h-3 w-full bg-bg-hover rounded" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header + filtres */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-bg-border">
        <div className="flex items-center gap-2">
          <TrendingUp size={14} className="text-signal-buy" />
          <span className="text-xs font-semibold text-text-primary">OPPORTUNITÉS</span>
          <span className="text-xxs text-text-muted num">{filtered.length}</span>
        </div>
        <div className="flex gap-1">
          {['BUY', 'ALL', 'NEUTRAL'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-xxs px-2 py-0.5 rounded font-mono transition-colors ${
                filter === f
                  ? 'bg-accent/20 text-accent'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Liste */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-xs text-text-muted">
            Aucune opportunité détectée
          </div>
        ) : (
          filtered.map((rec) => (
            <OpportunityRow
              key={rec.ticker}
              rec={rec}
              onClick={() => onSelectTicker?.(rec.ticker)}
            />
          ))
        )}
      </div>

      {/* Footer */}
      {lastUpdate && (
        <div className="px-3 py-1.5 border-t border-bg-border">
          <span className="text-xxs text-text-muted num">
            Mis à jour {fmt.time(lastUpdate?.toISOString())}
          </span>
        </div>
      )}
    </div>
  )
}


function OpportunityRow({ rec, onClick }) {
  const isPositive = rec.change_pct >= 0

  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-2.5 border-b border-bg-border hover:bg-bg-hover transition-colors group"
    >
      {/* Ligne 1 : ticker, nom, prix, variation */}
      <div className="flex items-center gap-2 mb-1.5">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="num text-sm font-bold text-text-primary">{rec.ticker.replace('.PA', '').replace('.DE', '').replace('.AS', '')}</span>
            <span className="text-xxs text-text-muted truncate hidden sm:block">{rec.name}</span>
          </div>
        </div>
        <div className="text-right">
          <div className={`num text-sm font-semibold ${isPositive ? 'text-gain' : 'text-loss'}`}>
            {fmt.price(rec.price)}
          </div>
          <div className={`num text-xxs ${variationColor(rec.change_pct)}`}>
            {fmt.pct(rec.change_pct)}
          </div>
        </div>
      </div>

      {/* Ligne 2 : signal + score + barre */}
      <div className="flex items-center gap-2 mb-1.5">
        <SignalBadge signal={rec.signal} />
        <div className="flex-1 flex items-center gap-1.5">
          <div className="flex-1 h-1 bg-bg-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${scoreBarColor(rec.score)}`}
              style={{ width: `${rec.score}%` }}
            />
          </div>
          <span className={`num text-xxs font-bold ${scoreColor(rec.score)}`}>
            {fmt.score(rec.score)}
          </span>
        </div>
        {rec.ai_analyzed && (
          <Sparkles size={10} className="text-gold flex-shrink-0" />
        )}
      </div>

      {/* Ligne 3 : cause */}
      {rec.cause && (
        <p className="text-xxs text-text-secondary leading-relaxed line-clamp-1">
          {rec.cause}
        </p>
      )}

      {/* Ligne 4 : horizon si dispo */}
      {rec.horizon && (
        <span className="text-xxs text-text-muted">
          Horizon : {rec.horizon}
        </span>
      )}
    </button>
  )
}
