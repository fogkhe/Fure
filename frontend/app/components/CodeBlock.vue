<script setup lang="ts">
import { classHighlighter, highlightTree } from '@lezer/highlight'
import { codeLanguages } from '~/utils/codeLanguage'
import type { CodeLanguage } from '~/utils/codeLanguage'

const props = defineProps<{ source: string, language?: CodeLanguage }>()

const tokens = computed(() => {
  const { source, language } = props
  if (!language) return [{ text: source, style: undefined }]

  const parts: { text: string, style?: string }[] = []
  let position = 0
  highlightTree(codeLanguages[language].language.parser.parse(source), classHighlighter, (from, to, style) => {
    if (from > position) parts.push({ text: source.slice(position, from) })
    parts.push({ text: source.slice(from, to), style })
    position = to
  })
  if (position < source.length) parts.push({ text: source.slice(position) })
  return parts
})
</script>

<template>
  <pre
    data-code-syntax
    class="whitespace-pre-wrap wrap-anywhere"
  ><code class="[font:inherit]"><template
    v-for="(token, index) in tokens"
    :key="index"
  ><span
    v-if="token.style"
    :class="token.style"
  >{{ token.text }}</span><template v-else>{{ token.text }}</template></template></code></pre>
</template>
