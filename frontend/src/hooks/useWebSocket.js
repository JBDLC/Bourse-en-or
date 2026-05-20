/**
 * hooks/useWebSocket.js
 * Hook WebSocket avec reconnexion automatique toutes les 5s
 */
import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
const RECONNECT_DELAY = 5000

export function useWebSocket() {
  const [status, setStatus] = useState('connecting') // connecting | connected | disconnected
  const [lastMessage, setLastMessage] = useState(null)
  const [quotes, setQuotes] = useState({})
  const [signals, setSignals] = useState({})
  const [alerts, setAlerts] = useState([])

  const ws = useRef(null)
  const reconnectTimer = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    if (ws.current?.readyState === WebSocket.OPEN) return

    try {
      setStatus('connecting')
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => {
        if (!mountedRef.current) return
        setStatus('connected')
        clearTimeout(reconnectTimer.current)
        console.log('[WS] Connecté')
      }

      ws.current.onmessage = (event) => {
        if (!mountedRef.current) return
        try {
          const msg = JSON.parse(event.data)
          setLastMessage(msg)

          switch (msg.type) {
            case 'snapshot':
              if (msg.data?.quotes) setQuotes(msg.data.quotes)
              break

            case 'quote_update':
              if (msg.data) {
                setQuotes(prev => {
                  const next = { ...prev }
                  Object.entries(msg.data).forEach(([ticker, data]) => {
                    next[ticker] = { ...(prev[ticker] || {}), ...data }
                  })
                  return next
                })
              }
              break

            case 'signal_update':
              if (msg.data?.top) {
                const newSignals = {}
                msg.data.top.forEach(rec => {
                  newSignals[rec.ticker] = rec
                })
                setSignals(prev => ({ ...prev, ...newSignals }))
              }
              break

            case 'alert':
              setAlerts(prev => [msg.data, ...prev].slice(0, 20))
              break

            case 'ping':
              // Keepalive, rien à faire
              break
          }
        } catch (e) {
          console.error('[WS] Parse error:', e)
        }
      }

      ws.current.onclose = () => {
        if (!mountedRef.current) return
        setStatus('disconnected')
        console.log('[WS] Déconnecté, reconnexion dans 5s...')
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY)
      }

      ws.current.onerror = (err) => {
        console.error('[WS] Erreur:', err)
        ws.current?.close()
      }

    } catch (e) {
      console.error('[WS] Connexion impossible:', e)
      setStatus('disconnected')
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  return { status, quotes, signals, alerts, lastMessage }
}
