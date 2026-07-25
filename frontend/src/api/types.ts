// Типы, зеркалящие Pydantic-схемы бэкенда (app/schemas).

export type KitStatus = 'draft' | 'published'
export type KitItemType = 'fixed' | 'flexible'

// Цены приходят из Decimal — в JSON это число или числовая строка.
export type Money = number | string

export interface Category {
  id: number
  slug: string
  name: string
}

export interface ShopMeta {
  id: number
  code: string
  name: string
}

export interface Meta {
  roles: string[]
  drive_types: string[]
  experience_levels: string[]
  categories: Category[]
  shops: ShopMeta[]
}

export type OfferStatus = 'all' | 'unmatched' | 'matched'

export interface Product {
  id: number
  name: string
  slug: string
  brand?: string | null
  category_id?: number | null
  image_url?: string | null
}

export interface ShopBrief {
  id: number
  code: string
  name: string
}

export interface Offer {
  id: number
  raw_title: string
  raw_category?: string | null
  price?: Money | null
  in_stock: boolean
  url: string
  product_id?: number | null
  shop: ShopBrief
}

export interface KitItem {
  id: number
  item_type: KitItemType
  title: string
  is_required: boolean
  sort_order: number
  product_id?: number | null
  product?: Product | null
  category_id?: number | null
  max_price?: Money | null
  attr_filters?: Record<string, unknown> | null
}

export interface Candidate {
  id: number
  product_id: number
  product_name: string
  is_pinned: boolean
  is_excluded: boolean
}

export interface ItemPricing {
  item_id: number
  title: string
  item_type: KitItemType
  is_required: boolean
  min_price?: Money | null
  max_price?: Money | null
  variant_count: number
}

export interface KitPricing {
  price_min?: Money | null
  price_max?: Money | null
  complete: boolean
  items: ItemPricing[]
}

export interface KitListItem {
  id: number
  slug: string
  name: string
  role?: string | null
  drive_type?: string | null
  experience_level?: string | null
  status: KitStatus
  image_url?: string | null
  pricing: KitPricing
}

export interface KitImage {
  id: number
  url: string
  is_cover: boolean
  sort_order: number
}

export interface Kit {
  id: number
  slug: string
  name: string
  description?: string | null
  role?: string | null
  drive_type?: string | null
  experience_level?: string | null
  status: KitStatus
  image_url?: string | null
  items: KitItem[]
  images: KitImage[]
  pricing: KitPricing
}

export interface FlexibleVariant {
  product_id: number
  name: string
  brand?: string | null
  min_price?: Money | null
}

export interface FlexiblePreview {
  item_id: number
  variants: FlexibleVariant[]
}

// --- Публичная витрина -----------------------------------------------------

export interface KitCard {
  id: number
  slug: string
  name: string
  role?: string | null
  drive_type?: string | null
  experience_level?: string | null
  image_url?: string | null
  price_min?: Money | null
  price_max?: Money | null
  complete: boolean
}

export interface KitCatalog {
  items: KitCard[]
  total: number
  page: number
  page_size: number
}

export interface ProductBrief {
  id: number
  name: string
  brand?: string | null
  image_url?: string | null
}

export interface OfferView {
  shop: ShopMeta
  price?: Money | null
  in_stock: boolean
  url: string
}

export interface VariantView {
  product: ProductBrief
  min_price?: Money | null
  offers: OfferView[]
}

export interface KitDetailItem {
  id: number
  title: string
  item_type: KitItemType
  is_required: boolean
  sort_order: number
  min_price?: Money | null
  max_price?: Money | null
  product?: ProductBrief | null
  offers: OfferView[]
  variants: VariantView[]
}

export interface KitDetail {
  id: number
  slug: string
  name: string
  description?: string | null
  role?: string | null
  drive_type?: string | null
  experience_level?: string | null
  image_url?: string | null
  price_min?: Money | null
  price_max?: Money | null
  complete: boolean
  items: KitDetailItem[]
}

// --- Умный поиск по товарам (сравнение цен, M9) ----------------------------

export interface ProductSearchRow {
  id: number
  slug: string
  name: string
  brand?: string | null
  image_url?: string | null
  price_min?: Money | null
  shops_count: number
}

export interface ProductSearchResult {
  items: ProductSearchRow[]
  total: number
}

export interface ProductComparison {
  id: number
  slug: string
  name: string
  brand?: string | null
  image_url?: string | null
  description?: string | null
  price_min?: Money | null
  price_max?: Money | null
  shops_count: number
  offers: OfferView[]
}

// --- Админ-управление товарами ---------------------------------------------

export type ProductSort = 'name' | 'created' | 'offers' | 'price_min'
export type SortOrder = 'asc' | 'desc'

export interface ProductRow {
  id: number
  name: string
  slug: string
  brand?: string | null
  category_id?: number | null
  category_name?: string | null
  image_url?: string | null
  offers_count: number
  shops_count: number
  price_min?: Money | null
  price_max?: Money | null
}

export interface ProductCatalog {
  items: ProductRow[]
  total: number
  page: number
  page_size: number
}

export interface ProductOfferRow {
  id: number
  shop: ShopBrief
  raw_title: string
  raw_category?: string | null
  price?: Money | null
  in_stock: boolean
  is_active: boolean
  url: string
}

export interface ProductDetail {
  id: number
  name: string
  slug: string
  brand?: string | null
  category_id?: number | null
  category_name?: string | null
  description?: string | null
  image_url?: string | null
  attrs: Record<string, unknown>
  match_key: string
  offers_count: number
  shops_count: number
  price_min?: Money | null
  price_max?: Money | null
  offers: ProductOfferRow[]
}

export interface ProductUpdate {
  name?: string | null
  brand?: string | null
  category_id?: number | null
  description?: string | null
  image_url?: string | null
  attrs?: Record<string, unknown> | null
}

export interface CreateFromOfferResult {
  product: ProductDetail
  created: boolean
}

export type BulkAction =
  | { action: 'set_category'; product_ids: number[]; category_id: number | null }
  | { action: 'set_brand'; product_ids: number[]; brand: string | null }
  | { action: 'delete'; product_ids: number[]; unlink_offers?: boolean }

export interface BulkItemResult {
  product_id: number
  ok: boolean
  error?: string | null
}

export interface BulkResult {
  processed: number
  succeeded: number
  results: BulkItemResult[]
}
