/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        luna: {
          bg:       '#09090f',
          surface:  '#111118',
          card:     '#16161f',
          border:   '#1e1e2e',
          primary:  '#8b5cf6',
          glow:     '#7c3aed',
          accent:   '#a78bfa',
          muted:    '#94a3b8',
          text:     '#e2e8f0',
          dim:      '#64748b',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'bounce-dots': 'bounceDots 1.4s ease-in-out infinite',
        'scan-line': 'scan-line 0.9s linear forwards',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        bounceDots: {
          '0%, 80%, 100%': { transform: 'scale(0)' },
          '40%': { transform: 'scale(1)' },
        },
        'scan-line': {
          '0%':   { top: '0%',   opacity: '1' },
          '100%': { top: '100%', opacity: '0' },
        },
      },
      boxShadow: {
        'luna': '0 0 40px rgba(139, 92, 246, 0.15)',
        'luna-lg': '0 0 80px rgba(139, 92, 246, 0.2)',
        'glow': '0 0 20px rgba(139, 92, 246, 0.4)',
      },
    },
  },
  plugins: [],
}
