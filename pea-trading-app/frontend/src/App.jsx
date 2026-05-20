/**
 * App.jsx — Layout principal 3 colonnes du dashboard Bourse en or
 * Colonne gauche : Watchlist
 * Centre : Liste des opportunités
 * Droite : Détail du ticker sélectionné
 */
import { useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import MarketOverview from './components/MarketOverview'
import OpportunityList from './components/OpportunityList'
import Watchlist from './components/Watchlist'
import TickerDetail from './components/TickerDetail'
import ConnectionStatus from './components/ConnectionStatus'
import { TrendingUp, Settings } from 'lucide-react'

export default function App() {
  const { status, quotes, signals, alerts } = useWebSocket()
  const [selectedTicker, setSelectedTicker] = useState(null)

  return (
    <div className="flex flex-col h-screen bg-bg-primary text-text-primary overflow-hidden">
      {/* ── Header ── */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-bg-border bg-bg-secondary flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <TrendingUp size={18} className="text-signal-buy" />
            <span className="text-sm font-bold tracking-tight">Bourse en or</span>
            <span className="text-xxs text-text-muted border border-bg-border rounded px-1.5 py-0.5">
              Saxo Bank · PEA
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Alertes récentes */}
          {alerts.length > 0 && (
            <div className="flex items-center gap-1.5 bg-gold/10 border border-gold/30 rounded px-2 py-1">
              <span className="text-xxs text-gold font-mono">
                🔔 {alerts[0]?.message || 'Nouvelle alerte'}
              </span>
            </div>
          )}
          <ConnectionStatus status={status} />
          <button className="text-text-muted hover:text-text-primary transition-colors">
            <Settings size={14} />
          </button>
        </div>
      </header>

      {/* ── Barre indices ── */}
      <MarketOverview />

      {/* ── Corps principal 3 colonnes ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Colonne gauche — Watchlist (fixe 220px) */}
        <aside className="w-[220px] flex-shrink-0 border-r border-bg-border flex flex-col">
          <Watchlist
            wsQuotes={quotes}
            onSelectTicker={setSelectedTicker}
          />
        </aside>

        {/* Colonne centre — Opportunités (flexible) */}
        <main className="flex-1 border-r border-bg-border flex flex-col min-w-0">
          <OpportunityList
            wsQuotes={quotes}
            onSelectTicker={setSelectedTicker}
          />
        </main>

        {/* Colonne droite — Détail (fixe 360px) */}
        <aside className="w-[360px] flex-shrink-0 flex flex-col">
          <TickerDetail
            ticker={selectedTicker}
            onClose={() => setSelectedTicker(null)}
          />
        </aside>

      </div>

      {/* ── Footer status ── */}
      <footer className="flex items-center justify-between px-4 py-1 border-t border-bg-border bg-bg-secondary text-xxs text-text-muted flex-shrink-0">
        <span>⚠️ Outil d'aide à la décision — pas un conseil financier</span>
        <span className="num">
          {Object.keys(quotes).length} tickers suivis · Refresh 15s
        </span>
      </footer>
    </div>
  )
}
