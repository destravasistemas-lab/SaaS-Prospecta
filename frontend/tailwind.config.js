/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Paleta principal remapeada para Azul Cristal / Ice Cyan / Safira
        indigo: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8', // Azul cristal claro
          500: '#0ea5e9', // Sky vibrante
          600: '#0284c7', // Azul cristal elétrico
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
          950: '#082f49',
        },
        // Paleta Crystal & Ice
        crystal: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
          dark: '#030712',
          card: '#070e22',
        },
        // Cores neon/accent remapeadas para Azul Cristal, Ice Cyan e Branco Puro
        neon: {
          pink: '#38bdf8',   // Azul cristal claro (substitui pink anterior)
          purple: '#0ea5e9', // Azul sky vibrante
          cyan: '#00f0ff',   // Ice Cyan puro
          ice: '#bae6fd',    // Gelo cristalino
          white: '#ffffff',  // Branco puro
        },
        brand: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        dark: {
          DEFAULT: '#030712',
          50: '#070e22',
          100: '#0b152d',
          200: '#111e3d',
          300: '#1e293b',
          400: '#475569',
          500: '#94a3b8',
          600: '#cbd5e1',
          700: '#f1f5f9',
        },
        surface: {
          DEFAULT: '#030712',
          card: '#070e22',
          hover: '#0d1838',
        },
      },
    },
  },
  plugins: [],
}
