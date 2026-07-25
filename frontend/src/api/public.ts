// API публичной витрины (без авторизации).

import { apiFetch } from './client'
import type {
  KitCard,
  KitCatalog,
  KitDetail,
  ProductComparison,
  ProductSearchResult,
} from './types'

export interface CatalogFilters {
  role?: string | null
  drive_type?: string | null
  budget_min?: number | null
  budget_max?: number | null
  page?: number
}

export const listKits = (filters: CatalogFilters = {}) => {
  const params = new URLSearchParams()
  if (filters.role) params.set('role', filters.role)
  if (filters.drive_type) params.set('drive_type', filters.drive_type)
  if (filters.budget_min != null) params.set('budget_min', String(filters.budget_min))
  if (filters.budget_max != null) params.set('budget_max', String(filters.budget_max))
  if (filters.page) params.set('page', String(filters.page))
  return apiFetch<KitCatalog>(`/kits?${params.toString()}`)
}

export const getKitDetail = (slug: string) => apiFetch<KitDetail>(`/kits/${slug}`)

export interface WizardAnswers {
  experience?: string | null
  role?: string | null
  budget?: number | null
}

export const recommend = (body: WizardAnswers) =>
  apiFetch<KitCard[]>('/wizard/recommend', { method: 'POST', body: JSON.stringify(body) })

export const searchKits = (q: string) =>
  apiFetch<KitCard[]>(`/search?q=${encodeURIComponent(q)}`)

// Умный поиск по отдельным товарам (сравнение цен, M9).
export const searchProducts = (q: string) =>
  apiFetch<ProductSearchResult>(`/products/search?q=${encodeURIComponent(q)}`)

export const getProductComparison = (slug: string) =>
  apiFetch<ProductComparison>(`/products/${slug}`)
