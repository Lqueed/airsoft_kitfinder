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
