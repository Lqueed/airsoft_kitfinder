// Форматирование цен и вилки цены кита.

import type { KitPricing, Money } from '../api/types'

const RUB = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

export function formatPrice(value: Money | null | undefined): string {
  if (value == null) return '—'
  const n = typeof value === 'string' ? Number(value) : value
  return Number.isFinite(n) ? `${RUB.format(n)} ₽` : '—'
}

export function formatMinMax(
  priceMin: Money | null | undefined,
  priceMax: Money | null | undefined,
  complete: boolean,
): string {
  if (!complete) return 'неполный'
  const min = formatPrice(priceMin)
  const max = formatPrice(priceMax)
  return min === max ? min : `${min} – ${max}`
}

export function formatRange(pricing: KitPricing): string {
  return formatMinMax(pricing.price_min, pricing.price_max, pricing.complete)
}
