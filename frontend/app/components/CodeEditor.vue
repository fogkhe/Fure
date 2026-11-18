<script setup lang="ts">
import { indentWithTab } from '@codemirror/commands'
import { indentUnit, syntaxHighlighting } from '@codemirror/language'
import { Annotation, Compartment, EditorState, Transaction } from '@codemirror/state'
import { EditorView, keymap } from '@codemirror/view'
import { classHighlighter } from '@lezer/highlight'
import { basicSetup } from 'codemirror'
import { codeLanguages, russianEditorPhrases } from '~/utils/codeLanguage'
import type { CodeLanguage } from '~/utils/codeLanguage'

const props = defineProps<{
  language: CodeLanguage | 'text'
  label: string
  rows: number
  expand?: boolean
  disabled?: boolean
  invalid?: boolean
}>()
const value = defineModel<string>({ required: true })
const host = useTemplateRef<HTMLDivElement>('host')
const { locale } = useI18n()
const { id, ariaAttrs, disabled, emitFormInput, emitFormFocus, emitFormBlur } = useFormField(props)
const languageConfig = new Compartment()
const fieldConfig = new Compartment()
const externalUpdate = Annotation.define<boolean>()
let editor: EditorView | undefined

function languageExtensions() {
  if (props.language === 'text') {
    return EditorState.languageData.of(() => [{ closeBrackets: { brackets: [] } }])
  }
  const spaces = props.language === 'python' ? 4 : 2
  return [codeLanguages[props.language], indentUnit.of(' '.repeat(spaces)), keymap.of([indentWithTab])]
}

function fieldExtensions() {
  return [
    EditorState.phrases.of(locale.value === 'ru' ? russianEditorPhrases : {}),
    EditorState.readOnly.of(!!disabled.value),
    EditorView.editable.of(!disabled.value),
    EditorView.contentAttributes.of({
      ...ariaAttrs.value,
      ...(id.value ? { id: id.value } : {}),
      'aria-label': props.label,
      'aria-invalid': String(props.invalid || ariaAttrs.value?.['aria-invalid'] || false),
      'aria-disabled': String(!!disabled.value),
      'spellcheck': 'false',
      'autocapitalize': 'off',
      'autocorrect': 'off'
    })
  ]
}

onMounted(() => {
  editor = new EditorView({
    doc: value.value,
    parent: host.value!,
    extensions: [
      basicSetup,
      EditorView.lineWrapping,
      syntaxHighlighting(classHighlighter),
      languageConfig.of(languageExtensions()),
      fieldConfig.of(fieldExtensions()),
      EditorView.domEventHandlers({
        focus: () => { emitFormFocus() },
        blur: () => { emitFormBlur() }
      }),
      EditorView.updateListener.of((update) => {
        if (!update.docChanged || update.transactions.every(transaction => transaction.annotation(externalUpdate))) return
        const source = update.state.doc.toString()
        if (source === value.value) return
        value.value = source
        emitFormInput()
      })
    ]
  })
})

watch(value, (source) => {
  if (!editor || editor.state.doc.toString() === source) return
  editor.dispatch({
    changes: { from: 0, to: editor.state.doc.length, insert: source },
    annotations: [Transaction.addToHistory.of(false), externalUpdate.of(true)]
  })
})
watch(() => props.language, () => {
  editor?.dispatch({ effects: languageConfig.reconfigure(languageExtensions()) })
})
watch([id, ariaAttrs, disabled, locale, () => props.label, () => props.invalid], () => {
  editor?.dispatch({ effects: fieldConfig.reconfigure(fieldExtensions()) })
})
onBeforeUnmount(() => editor?.destroy())
</script>

<template>
  <div
    ref="host"
    data-code-editor
    :data-expand="expand || undefined"
    data-code-syntax
    class="min-w-0 overflow-hidden rounded-md border border-default bg-default font-mono text-sm focus-within:border-primary"
    :class="{ 'border-error': invalid, 'opacity-60': disabled }"
    :style="{ '--code-editor-min-height': `${rows * 1.5 + 1}rem` }"
  />
</template>
