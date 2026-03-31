import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(false)

  function initialize() {
    const stored = localStorage.getItem('sentinel-theme')
    if (stored) {
      isDark.value = stored === 'dark'
    } else {
      isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
    }
    applyTheme()
  }

  function toggle() {
    isDark.value = !isDark.value
  }

  function applyTheme() {
    if (isDark.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  watch(isDark, () => {
    applyTheme()
    localStorage.setItem('sentinel-theme', isDark.value ? 'dark' : 'light')
  })

  return {
    isDark,
    initialize,
    toggle,
  }
})
