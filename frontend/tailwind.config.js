/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Accent neon (Aurora): remapeia toda a escala `indigo-*` já usada no app
        // para o roxo neon — re-tinge o sistema inteiro sem mexer tela por tela.
        indigo: {
          50: '#faf5ff',
          100: '#f3e8ff',
          200: '#e9d5ff',
          300: '#d8b4fe',
          400: '#c9a7ff',
          500: '#bd7cf9',
          600: '#a855f7',
          700: '#9333ea',
          800: '#7e22ce',
          900: '#4a1d7a',
        },
        // Cores neon da marca, disponíveis como classes (bg-neon-pink, text-neon-cyan…)
        neon: {
          pink: '#ff4fd8',
          purple: '#a855f7',
          cyan: '#00d4ff',
        },
        brand: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#4f46e5',
          600: '#4338ca',
          700: '#3730a3',
          800: '#312e81',
          900: '#1e1b4b',
        },
        dark: {
          DEFAULT: '#0f172a',
          50: '#1e293b',
          100: '#334155',
          200: '#475569',
          300: '#64748b',
          400: '#94a3b8',
          500: '#cbd5e1',
          600: '#e2e8f0',
          700: '#f1f5f9',
        },
        surface: {
          DEFAULT: '#0f172a',
          card: '#1e293b',
          hover: '#334155',
        },
      },
    },
  },
  plugins: [],
}
