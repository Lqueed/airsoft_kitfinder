// API публичной витрины (без авторизации).

import { apiFetch } from './client'
import type { KitCatalog, KitDetail } from './types'

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
