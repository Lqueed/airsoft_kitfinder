import { Select } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { searchProducts } from '../api/admin'

interface Props {
  onSelect: (productId: number) => void
  categoryId?: number | null
  label?: string
  placeholder?: string
}

// Асинхронный автокомплит товаров: печатаешь ≥2 символа → подгружает совпадения.
export function ProductPicker({ onSelect, categoryId, label, placeholder }: Props) {
  const [search, setSearch] = useState('')

  const { data: products } = useQuery({
    queryKey: ['products', search, categoryId],
    queryFn: () => searchProducts(search, categoryId),
    enabled: search.trim().length >= 2,
  })

  const options = (products ?? []).map((p) => ({ value: String(p.id), label: p.name }))

  return (
    <Select
      label={label}
      placeholder={placeholder ?? 'Начните вводить название'}
      searchable
      data={options}
      searchValue={search}
      onSearchChange={setSearch}
      nothingFoundMessage={search.length >= 2 ? 'Ничего не найдено' : 'Введите ≥2 символов'}
      onChange={(value) => {
        if (value) onSelect(Number(value))
      }}
    />
  )
}
