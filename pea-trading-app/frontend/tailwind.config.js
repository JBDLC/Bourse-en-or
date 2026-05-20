/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Fond principal — dark terminal
        bg: {
          primary:   '#0A0E17',
          secondary: '#111827',
          card:      '#141C2B',
          hover:     '#1A2540',
          border:    '#1E2D45',
        },
        // Signaux
        signal: {
          strong_buy:  '#00D4AA',
          buy:         '#00B894',
          neutral:     '#636E72',
          avoid:       '#FF6B6B',
          strong_avoid:'#FF4757',
        },
        // Variations prix
        gain:   '#00D4AA',
        loss:   '#FF4757',
        flat:   '#636E72',
        // Score
        score: {
          high:   '#FFB800',
          medium: '#FDA147',
          low:    '#636E72',
        },
        // Texte
        text: {
          primary:   '#E8EDF5',
          secondary: '#8892A4',
          muted:     '#4A5568',
        },
        // Accents
        accent: '#3D8EFF',
        gold:   '#FFB800',
      },
      fontFamily: {
        mono:  ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans:  ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'xxs': '0.65rem',
      },
      animation: {
        'flash-green': 'flashGreen 0.6s ease-out',
        'flash-red':   'flashRed 0.6s ease-out',
        'pulse-slow':  'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
      },
      keyframes: {
        flashGreen: {
          '0%':   { backgroundColor: 'rgba(0, 212, 170, 0.3)' },
          '100%': { backgroundColor: 'transparent' },
        },
        flashRed: {
          '0%':   { backgroundColor: 'rgba(255, 71, 87, 0.3)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
    },
  },
  plugins: [],
}
