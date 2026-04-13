import { ref, onMounted } from 'vue'

const STORAGE_KEY = 'sentinel_docs_theme'
const isDark = ref(false)

export function useDarkMode() {
  function apply(dark: boolean) {
    isDark.value = dark
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem(STORAGE_KEY, dark ? 'dark' : 'light')
  }

  function toggle() {
    apply(!isDark.value)
  }

  onMounted(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'dark') {
      apply(true)
    } else if (stored === 'light') {
      apply(false)
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      apply(true)
    }
  })

  return { isDark, toggle }
}
