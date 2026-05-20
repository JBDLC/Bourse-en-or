/**
 * components/Watchlist.jsx
 * Ma liste de suivi avec alertes de prix
 */
import { useEffect, useState } from 'react'
import { fmt, variationColor } from '../utils/formatters'
import SignalBadge from './SignalBadge'
import { Plus, Trash2, Bell, BellOff } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Watchlist({ wsQuotes, onSelectTicker }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [addMode, setAddMode] = useState(false)
  const [addTicker, setAddTicker] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    load()
  }, [])

  const load = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/watchlist`)
      if (res.ok) {
        const data = await res.json()
        setItems(data.watchlist || [])
      }
    } catch (e) {
      console.error('Erreur watchlist:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async () => {
    const ticker = addTicker.trim().toUpperCase()
    if (!ticker) return

    setAdding(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker }),
      })

      if (res.ok) {
        setAddTicker('')
        setAddMode(false)
        await load()
      } else {
        const err = await res.json()
        setError(err.detail || 'Erreur')
      }
    } catch (e) {
      setError('Erreur réseau')
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (ticker) => {
    try {
      await fetch(`${API_BASE}/api/watchlist/${ticker}`, { method: 'DELETE' })
      setItems(prev => prev.filter(i => i.ticker !== ticker))
    } catch (e) {
      console.error('Erreur suppression:', e)
    }
  }

  if (loading) {
    return (
      <div className="p-3 space-y-2 animate-pulse">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-10 bg-bg-hover rounded" />
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-bg-border">
        <div className="flex items-center gap-2">
          <Bell size={12} className="text-gold" />
          <span className="text-xs font-semibold text-text-primary">MA WATCHLIST</span>
          <span className="text-xxs text-text-muted num">{items.length}</span>
        </div>
        <button
          onClick={() => setAddMode(!addMode)}
          className="text-text-muted hover:text-accent transition-colors"
        >
          <Plus size={14} />
        </button>
      </div>

      {/* Formulaire ajout */}
      {addMode && (
        <div className="p-2 border-b border-bg-border bg-bg-hover/50">
          <div className="flex gap-1.5">
            <input
              type="text"
              value={addTicker}
              onChange={e => setAddTicker(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAdd()}
              placeholder="Ex: MC.PA"
              className="flex-1 bg-bg-primary border border-bg-border rounded px-2 py-1 text-xs text-text-primary placeholder-text-muted focus:outline-none focus:border-accent font-mono"
              autoFocus
            />
            <button
              onClick={handleAdd}
              disabled={adding}
              className="px-2 py-1 bg-accent/20 text-accent border border-accent/30 rounded text-xs hover:bg-accent/30 transition-colors"
            >
              {adding ? '...' : 'Ajouter'}
            </button>
          </div>
          {error && <p className="text-xxs text-loss mt-1">{error}</p>}
        </div>
      )}

      {/* Liste */}
      <div className="flex-1 overflow-y-auto">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-24 gap-2">
            <BellOff size={20} className="text-text-muted opacity-50" />
            <p className="text-xs text-text-muted">Watchlist vide</p>
          </div>
        ) : (
          items.map(item => {
            const ws = wsQuotes[item.ticker]
            const price = ws?.price ?? null
            const changePct = ws?.change_pct ?? null
            const signal = ws?.signal ?? null
            const score = ws?.score ?? null

            return (
              <button
                key={item.ticker}
                onClick={() => onSelectTicker?.(item.ticker)}
                className="w-full flex items-center gap-2 px-3 py-2.5 border-b border-bg-border hover:bg-bg-hover transition-colors text-left group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="num text-xs font-bold text-text-primary">
                      {item.ticker.replace('.PA', '').replace('.DE', '').replace('.AS', '')}
                    </span>
                    {signal && <SignalBadge signal={signal} />}
                  </div>
                  <span className="text-xxs text-text-muted truncate block">{item.name}</span>
                </div>

                <div className="text-right flex-shrink-0">
                  {price != null ? (
                    <>
                      <div className="num text-xs font-semibold text-text-primary">{fmt.price(price)}</div>
                      <div className={`num text-xxs ${variationColor(changePct)}`}>{fmt.pct(changePct)}</div>
                    </>
                  ) : (
                    <div className="text-xxs text-text-muted">–</div>
                  )}
                </div>

                <button
                  onClick={e => { e.stopPropagation(); handleRemove(item.ticker) }}
                  className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-loss transition-all p-0.5"
                >
                  <Trash2 size={11} />
                </button>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}
