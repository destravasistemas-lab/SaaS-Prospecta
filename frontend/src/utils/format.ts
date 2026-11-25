/** Formatação de números e dinheiro no idioma do painel e na moeda da conta. */
export function makeFormat(locale: string, currency = 'BRL') {
  const moneyFmt = new Intl.NumberFormat(locale, { style: 'currency', currency, currencyDisplay: 'narrowSymbol' })
  const intFmt = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 })
  const decFmt = new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return {
    money: (v: number) => moneyFmt.format(v || 0),
    int: (v: number) => intFmt.format(v || 0),
    dec: (v: number) => decFmt.format(v || 0),
    pct: (v: number) => `${decFmt.format(v || 0)}%`,
  }
}

/** Variação percentual entre dois períodos; null quando não dá para comparar. */
export function deltaPct(current: number, previous: number): number | null {
  if (!previous) return null
  return ((current - previous) / previous) * 100
}
