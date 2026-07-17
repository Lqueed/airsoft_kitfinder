import { Loader, Table, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'

import { previewItem } from '../api/admin'
import { formatPrice } from './format'

// Предпросмотр вариантов flexible-позиции с ценами.
export function PreviewModal({ itemId }: { itemId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['preview', itemId],
    queryFn: () => previewItem(itemId),
  })

  if (isLoading || !data) return <Loader />
  if (data.variants.length === 0) return <Text c="dimmed">Нет подходящих вариантов с ценой.</Text>

  return (
    <Table>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Товар</Table.Th>
          <Table.Th>Бренд</Table.Th>
          <Table.Th>Цена от</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {data.variants.map((v) => (
          <Table.Tr key={v.product_id}>
            <Table.Td>{v.name}</Table.Td>
            <Table.Td>{v.brand ?? '—'}</Table.Td>
            <Table.Td>{formatPrice(v.min_price)}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}
