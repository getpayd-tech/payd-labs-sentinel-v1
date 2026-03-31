import { useThemeStore } from '@/stores/theme'
import { storeToRefs } from 'pinia'

export function useTheme() {
  const themeStore = useThemeStore()
  const { isDark } = storeToRefs(themeStore)

  function toggle() {
    themeStore.toggle()
  }

  function initialize() {
    themeStore.initialize()
  }

  return {
    isDark,
    toggle,
    initialize,
  }
}
