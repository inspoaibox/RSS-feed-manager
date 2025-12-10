/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  safelist: [
    // 渐变主题所需的类
    'bg-gradient-to-br',
    'from-pink-400', 'via-rose-500', 'to-red-500',
    'from-cyan-400', 'via-cyan-500', 'to-blue-500',
    'from-yellow-400', 'via-orange-500', 'to-pink-500',
    'from-teal-400', 'via-cyan-500', 'to-blue-600',
    'shadow-rose-500/50', 'shadow-cyan-500/50', 'shadow-orange-500/50', 'shadow-teal-500/50',
    'blur-md', 'scale-105', 'scale-102',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: 'rgb(var(--color-primary-50) / <alpha-value>)',
          100: 'rgb(var(--color-primary-100) / <alpha-value>)',
          200: 'rgb(var(--color-primary-200) / <alpha-value>)',
          300: 'rgb(var(--color-primary-300) / <alpha-value>)',
          400: 'rgb(var(--color-primary-400) / <alpha-value>)',
          500: 'rgb(var(--color-primary-500) / <alpha-value>)',
          600: 'rgb(var(--color-primary-600) / <alpha-value>)',
          700: 'rgb(var(--color-primary-700) / <alpha-value>)',
          800: 'rgb(var(--color-primary-800) / <alpha-value>)',
          900: 'rgb(var(--color-primary-900) / <alpha-value>)',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
