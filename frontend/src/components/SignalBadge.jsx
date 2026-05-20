/**
 * components/SignalBadge.jsx
 * Badge coloré affichant un signal de trading
 */
import { signalBadgeClass, signalLabel } from '../utils/formatters'

export default function SignalBadge({ signal, size = 'sm' }) {
  if (!signal) return null

  const sizeClass = size === 'lg'
    ? 'px-3 py-1 text-xs'
    : 'px-2 py-0.5 text-xxs'

  return (
    <span className={`${signalBadgeClass(signal)} ${sizeClass} rounded font-mono font-semibold tracking-wider whitespace-nowrap`}>
      {signalLabel(signal)}
    </span>
  )
}
