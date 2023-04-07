
import React from 'react'


export function NumberLocale ({value, languageCode}) {
  const formatter = React.useMemo(() => new Intl.NumberFormat(languageCode), [languageCode])
  return <span>{formatter.format(value)}</span>
}
