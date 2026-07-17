// API-функции админки поверх apiFetch. Все запросы несут cookie-сессию.

import { apiFetch } from './client'
import type {
  FlexiblePreview,
  Kit,
  KitItem,
  KitListItem,
  Meta,
  Money,
  Offer,
  OfferStatus,
  Product,
} from './types'

// --- Аутентификация --------------------------------------------------------

export const getMe = () => apiFetch<{ admin: boolean }>('/admin/me')

export const login = (password: string) =>
  apiFetch<{ status: string }>('/admin/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  })

export const logout = () => apiFetch<{ status: string }>('/admin/logout', { method: 'POST' })

// --- Справочники -----------------------------------------------------------

export const getMeta = () => apiFetch<Meta>('/meta')

// --- Киты ------------------------------------------------------------------

export const listKits = () => apiFetch<KitListItem[]>('/admin/kits')

export const getKit = (id: number) => apiFetch<Kit>(`/admin/kits/${id}`)

export interface KitFields {
  name?: string
  description?: string | null
  role?: string | null
  drive_type?: string | null
  experience_level?: string | null
  image_url?: string | null
}

export const createKit = (body: KitFields) =>
  apiFetch<Kit>('/admin/kits', { method: 'POST', body: JSON.stringify(body) })

export const updateKit = (id: number, body: KitFields) =>
  apiFetch<Kit>(`/admin/kits/${id}`, { method: 'PATCH', body: JSON.stringify(body) })

export const deleteKit = (id: number) =>
  apiFetch<void>(`/admin/kits/${id}`, { method: 'DELETE' })

export const publishKit = (id: number) =>
  apiFetch<Kit>(`/admin/kits/${id}/publish`, { method: 'POST' })

export const unpublishKit = (id: number) =>
  apiFetch<Kit>(`/admin/kits/${id}/unpublish`, { method: 'POST' })

// --- Позиции кита ----------------------------------------------------------

export interface ItemFields {
  item_type?: KitItem['item_type']
  title?: string
  is_required?: boolean
  sort_order?: number
  product_id?: number | null
  category_id?: number | null
  max_price?: Money | null
  attr_filters?: Record<string, unknown> | null
}

export const addItem = (kitId: number, body: ItemFields) =>
  apiFetch<Kit>(`/admin/kits/${kitId}/items`, { method: 'POST', body: JSON.stringify(body) })

export const updateItem = (itemId: number, body: ItemFields) =>
  apiFetch<Kit>(`/admin/items/${itemId}`, { method: 'PATCH', body: JSON.stringify(body) })

export const deleteItem = (itemId: number) =>
  apiFetch<void>(`/admin/items/${itemId}`, { method: 'DELETE' })

export const previewItem = (itemId: number) =>
  apiFetch<FlexiblePreview>(`/admin/kit-items/${itemId}/preview`)

// --- Каталог (товары и офферы) ---------------------------------------------

export const searchProducts = (q: string, categoryId?: number | null) => {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (categoryId != null) params.set('category_id', String(categoryId))
  return apiFetch<Product[]>(`/admin/products?${params.toString()}`)
}

export interface OfferFilters {
  shop?: string | null
  q?: string
  status?: OfferStatus
  active?: boolean | null
}

export const listOffers = (filters: OfferFilters = {}) => {
  const params = new URLSearchParams()
  if (filters.shop) params.set('shop', filters.shop)
  if (filters.q) params.set('q', filters.q)
  if (filters.status) params.set('status', filters.status)
  if (filters.active != null) params.set('active', String(filters.active))
  return apiFetch<Offer[]>(`/admin/offers?${params.toString()}`)
}

export const linkOffer = (offerId: number, productId: number) =>
  apiFetch<Offer>(`/admin/offers/${offerId}/link`, {
    method: 'POST',
    body: JSON.stringify({ product_id: productId }),
  })
