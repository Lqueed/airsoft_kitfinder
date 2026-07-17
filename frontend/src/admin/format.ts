// Форматирование цен и вилки цены кита.

import type { KitPricing, Money } from '../api/types'

const RUB = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

export function formatPrice(value: Money | null | undefined): string {
  if (value == null) return '—'
  const n = typeof value === 'string' ? Number(value) : value
  return Number.isFinite(n) ? `${RUB.format(n)} ₽` : '—'
}

export function formatRange(pricing: KitPricing): string {
  if (!pricing.complete) return 'неполный'
  const min = formatPrice(pricing.price_min)
  const max = formatPrice(pricing.price_max)
  return min === max ? min : `${min} – ${max}`
}
