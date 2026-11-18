import { jinja } from '@codemirror/lang-jinja'
import { json } from '@codemirror/lang-json'
import { python } from '@codemirror/lang-python'

export const codeLanguages = {
  jinja: jinja(),
  json: json(),
  python: python()
}

export type CodeLanguage = keyof typeof codeLanguages

// CodeMirror uses the source phrase as its translation key.
export const russianEditorPhrases = {
  'Find': 'Найти',
  'Replace': 'Заменить на',
  'next': 'Далее',
  'previous': 'Назад',
  'all': 'Выделить все',
  'match case': 'Учитывать регистр',
  'regexp': 'Регулярное выражение',
  'by word': 'Целое слово',
  'replace': 'Заменить',
  'replace all': 'Заменить все',
  'close': 'Закрыть',
  'Go to line': 'Перейти к строке',
  'go': 'Перейти',
  'current match': 'Текущее совпадение',
  'on line': 'в строке',
  'replaced match on line $': 'Совпадение в строке $ заменено',
  'replaced $ matches': 'Заменено совпадений: $',
  'Fold line': 'Свернуть блок',
  'Unfold line': 'Развернуть блок',
  'Folded lines': 'Свёрнуты строки',
  'Unfolded lines': 'Развёрнуты строки',
  'to': 'по',
  'folded code': 'Свёрнутый код',
  'unfold': 'Развернуть',
  'Completions': 'Подсказки',
  'Control character': 'Управляющий символ'
}
