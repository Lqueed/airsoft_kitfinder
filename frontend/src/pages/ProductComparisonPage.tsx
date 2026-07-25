import {
  Anchor,
  Badge,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { getProductComparison } from '../api/public'
import type { OfferView } from '../api/types'
import { formatPrice } from '../admin/format'

// Строка таблицы сравнения: магазин, цена, наличие, ссылка «Купить».
function OfferRow({ offer }: { offer: OfferView }) {
  const available = offer.in_stock && offer.price != null
  return (
    <Table.Tr style={available ? undefined : { opacity: 0.55 }}>
      <Table.Td>{offer.shop.name}</Table.Td>
      <Table.Td>
        <Text fw={600}>{formatPrice(offer.price)}</Text>
      </Table.Td>
      <Table.Td>
        {offer.in_stock ? (
          <Badge variant="light" color="teal">
            в наличии
          </Badge>
        ) : (
          <Badge variant="light" color="gray">
            нет в наличии
          </Badge>
        )}
      </Table.Td>
      <Table.Td>
        <Anchor href={offer.url} target="_blank" rel="noopener nofollow" size="sm">
          Купить →
        </Anchor>
      </Table.Td>
    </Table.Tr>
  )
}

// Карточка товара: сравнение цен по магазинам (дешёвые/в наличии — сверху).
export function ProductComparisonPage() {
  const { slug } = useParams()
  const { data: product, isLoading, isError } = useQuery({
    queryKey: ['product-comparison', slug],
    queryFn: () => getProductComparison(slug as string),
    enabled: !!slug,
  })

  if (isLoading) return <Loader m="xl" />
  if (isError || !product) {
    return (
      <Container py="xl">
        <Text c="red">Товар не найден.</Text>
        <Anchor component={Link} to="/products">
          ← К поиску товаров
        </Anchor>
      </Container>
    )
  }

  return (
    <Container py="xl" size="md">
      <Anchor component={Link} to="/products" size="sm">
        ← К поиску товаров
      </Anchor>
      <Title order={1} mt="sm">
        {product.name}
      </Title>
      <Group gap="xs" mt="xs">
        {product.brand && <Badge variant="light">{product.brand}</Badge>}
        <Text c="dimmed" size="sm">
          Доступен в {product.shops_count}{' '}
          {product.shops_count === 1 ? 'магазине' : 'магазинах'}
        </Text>
      </Group>
      {product.description && (
        <Text mt="md" c="dimmed">
          {product.description}
        </Text>
      )}

      <Title order={3} mt="xl" mb="sm">
        Где купить
      </Title>
      {product.offers.length === 0 ? (
        <Text c="dimmed">Нет активных предложений.</Text>
      ) : (
        <Paper withBorder>
          <Table verticalSpacing="sm" horizontalSpacing="md">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Магазин</Table.Th>
                <Table.Th>Цена</Table.Th>
                <Table.Th>Наличие</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {product.offers.map((o) => (
                <OfferRow key={`${o.shop.id}-${o.url}`} offer={o} />
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}

      <Stack mt="lg" gap={2}>
        <Text size="sm" c="dimmed">
          Минимальная цена: <b>{formatPrice(product.price_min)}</b>
        </Text>
      </Stack>
    </Container>
  )
}
