/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./sidepanel.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: '#111315', // Main background
          subtle: '#191C1F',  // Secondary background
          elevated: '#202428',// Elevated surface
          hover: '#282D32',   // Hover state
          active: '#30363C',  // Active/selected state
        },
        content: {
          primary: '#F0F2F3',   // Primary text
          secondary: '#92999F', // Secondary / metadata text
          muted: '#62686F',     // Dimmed labels / shortcuts
        },
        edge: {
          DEFAULT: '#2A3035', // Borders
          subtle: '#202428',  // Subtle dividers
          strong: '#3B434A',  // Emphasized borders
        },
        teal: {
          DEFAULT: '#5CB8A5', // Restrained Muted Teal
          hover: '#4EA794',
          subtle: 'rgba(92, 184, 165, 0.10)',
          border: 'rgba(92, 184, 165, 0.25)',
          text: '#76CEBC',
        },
        coral: {
          DEFAULT: '#E06C75', // Restrained Red / Error
          subtle: 'rgba(224, 108, 117, 0.10)',
          border: 'rgba(224, 108, 117, 0.25)',
        },
        amber: {
          DEFAULT: '#E5C07B', // Restrained Warning
          subtle: 'rgba(229, 192, 123, 0.10)',
          border: 'rgba(229, 192, 123, 0.25)',
        }
      },
      fontFamily: {
        sans: [
          'Inter',
          'Geist',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          '"JetBrains Mono"',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '0.875rem' }],
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.8125rem', { lineHeight: '1.25rem' }],
        'base': ['0.875rem', { lineHeight: '1.375rem' }],
      },
      borderRadius: {
        'control': '5px',
        'panel': '8px',
      },
    },
  },
  plugins: [],
}
