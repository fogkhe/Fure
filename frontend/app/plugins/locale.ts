export default defineNuxtPlugin({
  name: 'locale-preference',
  dependsOn: ['i18n:plugin:route-locale-detect'],
  async setup(nuxtApp) {
    const preference = useCookie<'en' | 'ru'>('fure_locale', {
      path: '/', sameSite: 'lax', maxAge: 60 * 60 * 24 * 365
    })
    const i18n = nuxtApp.$i18n
    await i18n.setLocale(preference.value === 'ru' ? 'ru' : 'en')
    watch(i18n.locale, (locale) => {
      if (locale === 'en' || locale === 'ru') preference.value = locale
    }, { flush: 'sync' })
  }
})
