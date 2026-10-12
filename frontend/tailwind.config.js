/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        // Narxoz University red (#D50032) as brand-600; 600+ pass WCAG AA on white.
        brand: {
          50: '#fff1f3',
          100: '#ffe0e5',
          200: '#ffc2cc',
          300: '#ff8fa2',
          400: '#f5486a',
          500: '#e81a45',
          600: '#d50032',
          700: '#b0002a',
          800: '#8f0425',
          900: '#760823',
          950: '#43000f',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
};
