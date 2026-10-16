/** @type {import('tailwindcss').Config} */
import typography from '@tailwindcss/typography'
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: 'rgb(var(--rgb-primary-50) / <alpha-value>)',
          100: 'rgb(var(--rgb-primary-100) / <alpha-value>)',
          200: 'rgb(var(--rgb-primary-200) / <alpha-value>)',
          300: 'rgb(var(--rgb-primary-300) / <alpha-value>)',
          400: 'rgb(var(--rgb-primary-400) / <alpha-value>)',
          500: 'rgb(var(--rgb-primary-500) / <alpha-value>)',
          600: 'rgb(var(--rgb-primary-600) / <alpha-value>)',
          700: 'rgb(var(--rgb-primary-700) / <alpha-value>)',
          800: 'rgb(var(--rgb-primary-800) / <alpha-value>)',
          900: 'rgb(var(--rgb-primary-900) / <alpha-value>)',
        },
      },
    },
  },
  plugins: [
    typography,
  ],
}
