<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { Copy, Check } from 'lucide-vue-next'
import { useCodeHighlight } from '../../composables/useCodeHighlight'

const props = defineProps<{
  code: string
  language?: string
  title?: string
}>()

const { highlight } = useCodeHighlight()
const html = ref('')
const copied = ref(false)

async function render() {
  html.value = await highlight(props.code, props.language || 'json')
}

onMounted(render)
watch(() => props.code, render)

function copy() {
  navigator.clipboard.writeText(props.code)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}
</script>

<template>
  <div class="group relative rounded-xl border border-border overflow-hidden my-4">
    <div v-if="title" class="flex items-center justify-between px-4 py-2 bg-[#0d1117] border-b border-white/5">
      <span class="text-xs font-mono font-medium text-[#8b949e]">{{ title }}</span>
      <button
        @click="copy"
        class="flex items-center gap-1.5 px-2 py-1 rounded-md text-[#8b949e] hover:text-white hover:bg-white/10 transition-colors opacity-0 group-hover:opacity-100"
      >
        <Check v-if="copied" :size="13" class="text-accent" />
        <Copy v-else :size="13" />
        <span class="text-xs">{{ copied ? 'Copied' : 'Copy' }}</span>
      </button>
    </div>

    <button
      v-if="!title"
      @click="copy"
      class="absolute top-2 right-2 flex items-center gap-1.5 px-2 py-1 rounded-md text-[#8b949e] hover:text-white hover:bg-white/10 transition-colors opacity-0 group-hover:opacity-100 z-10"
    >
      <Check v-if="copied" :size="13" class="text-accent" />
      <Copy v-else :size="13" />
    </button>

    <div
      v-if="html"
      v-html="html"
      class="[&_pre]:!bg-[#0d1117] [&_pre]:!p-5 [&_pre]:!m-0 [&_pre]:overflow-x-auto [&_pre]:text-[0.8125rem] [&_pre]:leading-[1.7] [&_code]:!font-mono"
    />
    <pre v-else class="bg-[#0d1117] p-5 overflow-x-auto text-[0.8125rem] leading-[1.7]"><code class="text-[#e6edf3] font-mono">{{ code }}</code></pre>
  </div>
</template>
