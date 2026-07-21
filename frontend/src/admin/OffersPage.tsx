import {
  Anchor,
  Badge,
  Button,
  Group,
  Loader,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { createProductFromOffer, getMeta, linkOffer, listOffers } from '../api/admin'
import type { OfferStatus } from '../api/types'
import { formatPrice } from './format'
import { ProductPicker } from './ProductPicker'

// Каталог магазинов: поиск по сырым офферам конкретного магазина (независимо
// от матчинга) + ручная привязка к товару.
export function OffersPage() {
  const queryClient = useQueryClient()
  const [shop, setShop] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<OfferStatus>('all')

  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: getMeta })

  const filters = { shop, q: q.trim(), status }
  const { data: offers, isLoading } = useQuery({
    queryKey: ['offers', filters],
    queryFn: () => listOffers(filters),
  })

  const link = useMutation({
    mutationFn: ({ offerId, productId }: { offerId: number; productId: number }) =>
      linkOffer(offerId, productId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['offers'] }),
  })

  const createProduct = useMutation({
    mutationFn: (offerId: number) => createProductFromOffer(offerId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['offers'] }),
  })

  return (
    <Stack>
      <Title order={2}>Каталог магазинов</Title>

      <Group align="flex-end">
        <Select
          label="Магазин"
          placeholder="Все магазины"
          clearable
          w={220}
          data={(meta?.shops ?? []).map((s) => ({ value: s.code, label: s.name }))}
          value={shop}
          onChange={setShop}
        />
        <TextInput
          label="Поиск по названию"
          placeholder="напр. Exact 0.25"
          value={q}
          onChange={(e) => setQ(e.currentTarget.value)}
          w={280}
        />
        <SegmentedControl
          value={status}
          onChange={(v) => setStatus(v as OfferStatus)}
          data={[
            { label: 'Все', value: 'all' },
            { label: 'Несматченные', value: 'unmatched' },
            { label: 'Сматченные', value: 'matched' },
          ]}
        />
      </Group>

      {isLoading && <Loader />}
      {offers && offers.length === 0 && <Text c="dimmed">Ничего не найдено.</Text>}

      {offers && offers.length > 0 && (
        <Table verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Магазин</Table.Th>
              <Table.Th>Название на сайте</Table.Th>
              <Table.Th>Цена</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Привязать к товару</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {offers.map((offer) => (
              <Table.Tr key={offer.id}>
                <Table.Td>
                  <Badge variant="light">{offer.shop.name}</Badge>
                </Table.Td>
                <Table.Td>
                  <Anchor href={offer.url} target="_blank" rel="noopener nofollow" size="sm">
                    {offer.raw_title}
                  </Anchor>
                  {!offer.in_stock && (
                    <Badge color="gray" size="xs" ml="xs">
                      нет в наличии
                    </Badge>
                  )}
                </Table.Td>
                <Table.Td>{formatPrice(offer.price)}</Table.Td>
                <Table.Td>
                  {offer.product_id ? (
                    <Badge color="green" variant="light">
                      сматчен
                    </Badge>
                  ) : (
                    <Badge color="orange" variant="light">
                      нет
                    </Badge>
                  )}
                </Table.Td>
                <Table.Td w={320}>
                  <Group gap="xs" wrap="nowrap" align="flex-end">
                    <ProductPicker
                      onSelect={(productId) => link.mutate({ offerId: offer.id, productId })}
                      placeholder={offer.product_id ? 'Перепривязать…' : 'Найти товар…'}
                    />
                    {!offer.product_id && (
                      <Button
                        size="xs"
                        variant="light"
                        onClick={() => createProduct.mutate(offer.id)}
                        loading={createProduct.isPending && createProduct.variables === offer.id}
                      >
                        Создать товар
                      </Button>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  )
}
