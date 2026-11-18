export default defineI18nConfig(() => ({
  legacy: false,
  fallbackLocale: 'en',
  pluralRules: {
    ru: (choice: number, choicesLength: number) => {
      const count = Math.abs(choice)
      const last = count % 10
      const lastTwo = count % 100
      const form = last === 1 && lastTwo !== 11 ? 0 : last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? 1 : 2
      return choicesLength === 4 ? count === 0 ? 0 : form + 1 : form
    }
  }
}))
