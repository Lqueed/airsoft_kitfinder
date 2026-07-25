import {
  Anchor,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { searchProducts } from '../api/public'
import type { ProductSearchRow } from '../api/types'
import { formatPrice } from '../admin/format'

// Строка результата: товар, минимальная цена и число магазинов, где он есть.
function ProductRow({ product }: { product: ProductSearchRow }) {
  return (
    <Paper
      withBorder
      p="md"
      component={Link}
      to={`/products/${product.slug}`}
      style={{ textDecoration: 'none', color: 'inherit' }}
    >
      <Group justify="space-between" wrap="nowrap">
        <div>
          <Text fw={600}>{product.name}</Text>
          {product.brand && (
            <Text size="sm" c="dimmed">
              {product.brand}
            </Text>
          )}
        </div>
        <Stack gap={2} align="flex-end" style={{ flexShrink: 0 }}>
          <Text fw={700}>от {formatPrice(product.price_min)}</Text>
          <Badge variant="light" color="teal">
            {product.shops_count}{' '}
            {product.shops_count === 1 ? 'магазин' : 'магазинов'}
          </Badge>
        </Stack>
      </Group>
    </Paper>
  )
}

// Умный поиск по отдельным товарам: найти конкретный товар и увидеть, где дешевле.
export function ProductSearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const [query, setQuery] = useState(q)

  const { data, isLoading } = useQuery({
    queryKey: ['product-search', q],
    queryFn: () => searchProducts(q),
    enabled: q.trim().length >= 2,
  })

  return (
    <Container py="xl" size="md">
      <Anchor component={Link} to="/" size="sm">
        ← В каталог китов
      </Anchor>
      <Title order={1} mt="sm" mb="xs">
        Сравнение цен на товары
      </Title>
      <Text c="dimmed" mb="md">
        Найдите конкретный товар и посмотрите, в каком магазине он дешевле.
      </Text>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          setParams(query.trim().length >= 2 ? { q: query.trim() } : {})
        }}
      >
        <Group mb="lg">
          <TextInput
            placeholder="Название товара, бренд или модель…"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            w={360}
            autoFocus
          />
          <Button type="submit" disabled={query.trim().length < 2}>
            Найти
          </Button>
        </Group>
      </form>

      {isLoading && <Loader />}
      {q.trim().length >= 2 && data && data.items.length === 0 && (
        <Text c="dimmed">По запросу «{q}» ничего не найдено.</Text>
      )}
      {data && data.items.length > 0 && (
        <Stack>
          {data.items.map((p) => (
            <ProductRow key={p.id} product={p} />
          ))}
        </Stack>
      )}
    </Container>
  )
}
