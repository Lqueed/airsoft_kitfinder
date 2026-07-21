// API-функции админки поверх apiFetch. Все запросы несут cookie-сессию.

import { apiFetch } from './client'
import type {
  BulkAction,
  BulkResult,
  Candidate,
  CreateFromOfferResult,
  FlexiblePreview,
  Kit,
  KitItem,
  KitListItem,
  Meta,
  Money,
  Offer,
  OfferStatus,
  Product,
  ProductCatalog,
  ProductDetail,
  ProductSort,
  ProductUpdate,
  SortOrder,
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

// --- Фото кита -------------------------------------------------------------

export const uploadKitImages = (kitId: number, files: File[]) => {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  return apiFetch<Kit>(`/admin/kits/${kitId}/images`, { method: 'POST', body: fd })
}

export const deleteKitImage = (imageId: number) =>
  apiFetch<void>(`/admin/kit-images/${imageId}`, { method: 'DELETE' })

export const setKitCover = (imageId: number) =>
  apiFetch<Kit>(`/admin/kit-images/${imageId}/cover`, { method: 'POST' })

export const listCandidates = (itemId: number) =>
  apiFetch<Candidate[]>(`/admin/kit-items/${itemId}/candidates`)

export const upsertCandidate = (
  itemId: number,
  body: { product_id: number; is_pinned?: boolean; is_excluded?: boolean },
) =>
  apiFetch<Candidate[]>(`/admin/kit-items/${itemId}/candidates`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })

// --- Каталог (товары и офферы) ---------------------------------------------

export const searchProducts = (q: string, categoryId?: number | null) => {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (categoryId != null) params.set('category_id', String(categoryId))
  return apiFetch<Product[]>(`/admin/product-search?${params.toString()}`)
}

// --- Управление товарами (products) ----------------------------------------

export interface ProductFilters {
  q?: string
  category_id?: number | null
  no_category?: boolean
  multishop?: boolean
  sort?: ProductSort
  order?: SortOrder
  page?: number
  page_size?: number
}

export const listProducts = (filters: ProductFilters = {}) => {
  const params = new URLSearchParams()
  if (filters.q) params.set('q', filters.q)
  if (filters.category_id != null) params.set('category_id', String(filters.category_id))
  if (filters.no_category) params.set('no_category', 'true')
  if (filters.multishop) params.set('multishop', 'true')
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.order) params.set('order', filters.order)
  if (filters.page) params.set('page', String(filters.page))
  if (filters.page_size) params.set('page_size', String(filters.page_size))
  return apiFetch<ProductCatalog>(`/admin/products?${params.toString()}`)
}

export const getProduct = (id: number) => apiFetch<ProductDetail>(`/admin/products/${id}`)

export const updateProduct = (id: number, body: ProductUpdate) =>
  apiFetch<ProductDetail>(`/admin/products/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })

export const deleteProduct = (id: number) =>
  apiFetch<void>(`/admin/products/${id}`, { method: 'DELETE' })

export const mergeProducts = (targetId: number, sourceIds: number[]) =>
  apiFetch<ProductDetail>(`/admin/products/${targetId}/merge`, {
    method: 'POST',
    body: JSON.stringify({ source_ids: sourceIds }),
  })

export const bulkProducts = (body: BulkAction) =>
  apiFetch<BulkResult>('/admin/products/bulk', { method: 'POST', body: JSON.stringify(body) })

export const unlinkOffer = (offerId: number) =>
  apiFetch<Offer>(`/admin/offers/${offerId}/unlink`, { method: 'POST' })

export const createProductFromOffer = (offerId: number) =>
  apiFetch<CreateFromOfferResult>(`/admin/offers/${offerId}/create-product`, { method: 'POST' })

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
