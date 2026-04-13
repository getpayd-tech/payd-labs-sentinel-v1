import { ref } from 'vue'
import { createHighlighter, type Highlighter } from 'shiki'

let highlighter: Highlighter | null = null
const loading = ref(false)

export function useCodeHighlight() {
  async function highlight(code: string, lang: string = 'json'): Promise<string> {
    if (!highlighter) {
      loading.value = true
      highlighter = await createHighlighter({
        themes: ['github-dark-default'],
        langs: ['json', 'bash', 'javascript', 'typescript', 'python', 'yaml', 'toml', 'http'],
      })
      loading.value = false
    }

    try {
      return highlighter.codeToHtml(code, {
        lang,
        theme: 'github-dark-default',
      })
    } catch {
      return `<pre class="shiki"><code>${code}</code></pre>`
    }
  }

  return { highlight, loading }
}
