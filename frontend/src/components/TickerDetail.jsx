/**
 * components/TickerDetail.jsx
 * Panneau de détail d'un ticker sélectionné avec graphique + analyse IA
 */
import { useEffect, useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import { fmt, signalLabel, scoreColor, variationColor } from '../utils/formatters'
import SignalBadge from './SignalBadge'
import { Sparkles, ExternalLink, X, TrendingUp, TrendingDown, Minus } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function TickerDetail({ ticker, onClose }) {
  const [data, setData] = useState(null)
  const [news, setNews] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!ticker) return
    setLoading(true)

    const load = async () => {
      try {
        const [quoteRes, newsRes] = await Promise.all([
          fetch(`${API_BASE}/api/quotes/${ticker}`),
          fetch(`${API_BASE}/api/news/${ticker}`),
        ])

        if (quoteRes.ok) setData(await quoteRes.json())
        if (newsRes.ok) {
          const n = await newsRes.json()
          setNews(n.news || [])
        }
      } catch (e) {
        console.error('Erreur détail:', e)
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [ticker])

  if (!ticker) return (
    <div className="flex items-center justify-center h-full text-text-muted text-sm">
      <div className="text-center">
        <TrendingUp size={32} className="mx-auto mb-3 opacity-30" />
        <p>Sélectionnez un ticker pour voir l'analyse</p>
      </div>
    </div>
  )

  if (loading) return (
    <div className="p-4 space-y-3 animate-pulse">
      <div className="h-6 w-32 bg-bg-hover rounded" />
      <div className="h-40 bg-bg-hover rounded" />
      <div className="h-4 w-full bg-bg-hover rounded" />
      <div className="h-4 w-3/4 bg-bg-hover rounded" />
    </div>
  )

  if (!data) return (
    <div className="flex items-center justify-center h-full text-text-muted text-sm">
      Données non disponibles
    </div>
  )

  const ind = data.indicators || {}
  const isPositive = data.change_pct >= 0

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-bg-border">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="num text-xl font-bold text-text-primary">{ticker}</h2>
            <SignalBadge signal={data.signal} size="lg" />
          </div>
          <p className="text-sm text-text-secondary mt-0.5">{data.name}</p>
        </div>
        <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors p-1">
          <X size={16} />
        </button>
      </div>

      {/* Prix principal */}
      <div className="px-4 py-3 border-b border-bg-border">
        <div className="flex items-baseline gap-3">
          <span className="num text-3xl font-bold text-text-primary">{fmt.price(data.price)}</span>
          <span className={`num text-lg font-semibold ${variationColor(data.change_pct)}`}>
            {fmt.pct(data.change_pct)}
          </span>
        </div>

        {/* Score bar */}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xxs text-text-muted">Score</span>
          <div className="flex-1 h-1.5 bg-bg-border rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                data.score >= 70 ? 'bg-signal-buy' :
                data.score >= 45 ? 'bg-score-medium' : 'bg-signal-avoid'
              }`}
              style={{ width: `${data.score}%` }}
            />
          </div>
          <span className={`num text-sm font-bold ${scoreColor(data.score)}`}>
            {data.score}/100
          </span>
        </div>
      </div>

      {/* Indicateurs techniques */}
      <div className="px-4 py-3 border-b border-bg-border">
        <h3 className="text-xxs text-text-muted uppercase tracking-wider mb-2">Indicateurs</h3>
        <div className="grid grid-cols-2 gap-2">
          <IndicatorRow label="RSI 14" value={fmt.rsi(ind.rsi_14)} warning={ind.rsi_14 > 70 || ind.rsi_14 < 30} />
          <IndicatorRow label="MACD" value={ind.macd_hist?.toFixed(3)} positive={ind.macd_hist > 0} />
          <IndicatorRow label="BB Position" value={ind.bb_position ? `${(ind.bb_position * 100).toFixed(0)}%` : '—'} />
          <IndicatorRow label="Volume ratio" value={data.volume_ratio ? `${data.volume_ratio}x` : '—'} positive={data.volume_ratio > 1.2} />
          <IndicatorRow label="SMA 20" value={fmt.price(ind.sma_20)} />
          <IndicatorRow label="Trend 1W" value={ind.trend_1w} positive={ind.trend_1w === 'UP'} />
        </div>
      </div>

      {/* Analyse IA si disponible */}
      {data.cause && (
        <div className="px-4 py-3 border-b border-bg-border">
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles size={12} className="text-gold" />
            <h3 className="text-xxs text-gold uppercase tracking-wider">Analyse IA</h3>
          </div>
          <div className="space-y-2">
            {data.cause && (
              <div>
                <span className="text-xxs text-text-muted">Cause</span>
                <p className="text-xs text-text-secondary mt-0.5">{data.cause}</p>
              </div>
            )}
            {data.opportunity && (
              <div>
                <span className="text-xxs text-text-muted">Opportunité</span>
                <p className="text-xs text-signal-buy mt-0.5">{data.opportunity}</p>
              </div>
            )}
            {data.risk && (
              <div>
                <span className="text-xxs text-text-muted">Risque</span>
                <p className="text-xs text-signal-avoid mt-0.5">{data.risk}</p>
              </div>
            )}
            {data.horizon && (
              <div className="flex items-center gap-1">
                <span className="text-xxs text-text-muted">Horizon :</span>
                <span className="text-xs num text-accent font-semibold">{data.horizon}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* News récentes */}
      {news.length > 0 && (
        <div className="px-4 py-3">
          <h3 className="text-xxs text-text-muted uppercase tracking-wider mb-2">Actualités</h3>
          <div className="space-y-2">
            {news.map((item, i) => (
              <a
                key={i}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block group"
              >
                <div className="flex items-start gap-1.5">
                  <span className={`mt-0.5 flex-shrink-0 w-1.5 h-1.5 rounded-full ${
                    item.sentiment === 'POSITIVE' ? 'bg-gain' :
                    item.sentiment === 'NEGATIVE' ? 'bg-loss' : 'bg-flat'
                  }`} />
                  <div>
                    <p className="text-xs text-text-secondary group-hover:text-text-primary transition-colors leading-snug">
                      {item.headline}
                    </p>
                    <p className="text-xxs text-text-muted mt-0.5">
                      {item.source} · {fmt.date(item.published_at)}
                    </p>
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


function IndicatorRow({ label, value, positive, warning }) {
  let valueClass = 'text-text-primary'
  if (positive === true) valueClass = 'text-gain'
  else if (positive === false) valueClass = 'text-loss'
  if (warning) valueClass = 'text-gold'

  return (
    <div className="flex justify-between items-center">
      <span className="text-xxs text-text-muted">{label}</span>
      <span className={`num text-xs font-semibold ${valueClass}`}>{value || '—'}</span>
    </div>
  )
}
