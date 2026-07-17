import { Anchor, Badge, Group, Loader, Stack, Table, Text, Title } from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { linkOffer, listOffers } from '../api/admin'
import { formatPrice } from './format'
import { ProductPicker } from './ProductPicker'

// Экран ручной доразметки: несматченные офферы + привязка к товару.
export function OffersPage() {
  const queryClient = useQueryClient()
  const { data: offers, isLoading } = useQuery({
    queryKey: ['offers', 'unmatched'],
    queryFn: () => listOffers(true),
  })

  const link = useMutation({
    mutationFn: ({ offerId, productId }: { offerId: number; productId: number }) =>
      linkOffer(offerId, productId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['offers', 'unmatched'] }),
  })

  return (
    <Stack>
      <Title order={2}>Несматченные офферы</Title>
      {isLoading && <Loader />}
      {offers && offers.length === 0 && (
        <Text c="dimmed">Все офферы привязаны к товарам 🎉</Text>
      )}
      {offers && offers.length > 0 && (
        <Table verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Магазин</Table.Th>
              <Table.Th>Название на сайте</Table.Th>
              <Table.Th>Цена</Table.Th>
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
                </Table.Td>
                <Table.Td>{formatPrice(offer.price)}</Table.Td>
                <Table.Td w={320}>
                  <Group gap="xs">
                    <ProductPicker
                      onSelect={(productId) => link.mutate({ offerId: offer.id, productId })}
                      placeholder="Найти товар…"
                    />
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
