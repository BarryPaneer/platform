import React from 'react'


export function formatLanguage (language, displayLanguage) {
    if (!window.Intl || !window.Intl.DisplayNames) return language

    const capitalize = s => s.charAt(0).toUpperCase() + s.slice(1)
    const languageNames = new Intl.DisplayNames([displayLanguage || 'en'], {type: 'language'})
    return capitalize(languageNames.of((language || 'en').split(/[-_]/)[0]))
}

export default function LanguageLocale ({language, displayLanguage}) {
    return <span>{formatLanguage(language, displayLanguage)}</span>
}
