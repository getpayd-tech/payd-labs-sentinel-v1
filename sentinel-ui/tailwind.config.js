/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    screens: {
      xs: '375px',
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1536px',
    },
    extend: {
      fontFamily: {
        heading: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Nunito"', 'sans-serif'],
      },
      colors: {
        // CSS variable-based colors — automatically adapt to dark mode
        surface: {
          DEFAULT: 'var(--color-surface)',
          secondary: 'var(--color-surface-secondary)',
          tertiary: 'var(--color-surface-tertiary)',
        },
        border: {
          DEFAULT: 'var(--color-border)',
          medium: 'var(--color-border-medium)',
        },
        text: {
          DEFAULT: 'var(--color-text)',
          secondary: 'var(--color-text-secondary)',
          tertiary: 'var(--color-text-tertiary)',
        },
        accent: {
          DEFAULT: '#18D26E',
          light: '#4ae08e',
          dark: '#12a557',
          50: 'rgba(24, 210, 110, 0.05)',
          100: 'rgba(24, 210, 110, 0.1)',
          200: 'rgba(24, 210, 110, 0.2)',
          300: 'rgba(24, 210, 110, 0.3)',
        },
        kPrimary: {
          DEFAULT: '#10263E',
          light: '#1a3a5c',
          dark: '#0a1829',
          50: 'rgba(16, 38, 62, 0.05)',
          100: 'rgba(16, 38, 62, 0.1)',
          200: 'rgba(16, 38, 62, 0.2)',
        },
        gray: {
          DEFAULT: '#6b7280',
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#9ca3af',
          500: '#6b7280',
          600: '#4b5563',
          700: '#374151',
          800: '#1f2937',
          900: '#111827',
        },
        success: '#18D26E',
        warning: '#f59e0b',
        error: '#ef4444',
        info: '#3b82f6',
        red: {
          DEFAULT: '#ef4444', 50: '#fef2f2', 100: '#fee2e2', 200: '#fecaca',
          300: '#fca5a5', 400: '#f87171', 500: '#ef4444', 600: '#dc2626',
          700: '#b91c1c', 800: '#991b1b', 900: '#7f1d1d',
        },
        yellow: {
          DEFAULT: '#f59e0b', 50: '#fffbeb', 100: '#fef3c7', 200: '#fde68a',
          300: '#fcd34d', 400: '#fbbf24', 500: '#f59e0b', 600: '#d97706',
          700: '#b45309', 800: '#92400e', 900: '#78350f',
        },
        blue: {
          DEFAULT: '#3b82f6', 50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe',
          300: '#93c5fd', 400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb',
          700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a',
        },
        emerald: {
          DEFAULT: '#10b981', 50: '#ecfdf5', 100: '#d1fae5', 200: '#a7f3d0',
          300: '#6ee7b7', 400: '#34d399', 500: '#10b981', 600: '#059669',
          700: '#047857', 800: '#065f46', 900: '#064e3b',
        },
        purple: {
          DEFAULT: '#8b5cf6', 50: '#faf5ff', 100: '#f3e8ff', 200: '#e9d5ff',
          300: '#d8b4fe', 400: '#c084fc', 500: '#a855f7', 600: '#9333ea',
          700: '#7c3aed', 800: '#6b21a8', 900: '#581c87',
        },
        orange: {
          DEFAULT: '#f97316', 50: '#fff7ed', 100: '#ffedd5', 200: '#fed7aa',
          300: '#fdba74', 400: '#fb923c', 500: '#f97316', 600: '#ea580c',
          700: '#c2410c', 800: '#9a3412', 900: '#7c2d12',
        },
        'border-light': '#e2e8f0',
        'border-medium': '#cbd5e1',
      },
      spacing: {
        18: '4.5rem',
        22: '5.5rem',
        30: '7.5rem',
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      borderRadius: {
        '4xl': '2rem',
      },
      boxShadow: {
        soft: '0 2px 8px -2px rgba(16, 38, 62, 0.08)',
        medium: '0 4px 16px -4px rgba(16, 38, 62, 0.12)',
        strong: '0 8px 24px -8px rgba(16, 38, 62, 0.16)',
        'glow-accent': '0 0 20px -5px rgba(24, 210, 110, 0.4)',
        'glow-primary': '0 0 20px -5px rgba(16, 38, 62, 0.3)',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-down': {
          from: { opacity: '0', transform: 'translateY(-10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(20px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'slide-in-left': {
          from: { opacity: '0', transform: 'translateX(-20px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'slide-in-up': {
          from: { opacity: '0', transform: 'translateY(100%)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out',
        'fade-in-up': 'fade-in-up 0.4s ease-out',
        'fade-in-down': 'fade-in-down 0.4s ease-out',
        'slide-in-right': 'slide-in-right 0.3s ease-out',
        'slide-in-left': 'slide-in-left 0.3s ease-out',
        'slide-in-up': 'slide-in-up 0.3s ease-out',
        'scale-in': 'scale-in 0.2s ease-out',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        shimmer: 'shimmer 1.5s ease-in-out infinite',
      },
      transitionTimingFunction: {
        'bounce-in': 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
