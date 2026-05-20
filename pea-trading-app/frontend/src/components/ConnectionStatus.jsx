/**
 * components/ConnectionStatus.jsx
 * Indicateur de connexion WebSocket dans le header
 */
export default function ConnectionStatus({ status }) {
  const config = {
    connected: {
      dot: 'bg-gain animate-pulse',
      label: 'LIVE',
      text: 'text-gain',
    },
    connecting: {
      dot: 'bg-score-medium animate-pulse',
      label: 'CONNEXION...',
      text: 'text-score-medium',
    },
    disconnected: {
      dot: 'bg-loss',
      label: 'DÉCONNECTÉ',
      text: 'text-loss',
    },
  }

  const { dot, label, text } = config[status] || config.disconnected

  return (
    <div className={`flex items-center gap-1.5 text-xxs font-mono font-medium ${text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </div>
  )
}
