import { Badge, Button, Divider, Group, Loader, Stack, Table, Text } from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { listCandidates, previewItem, upsertCandidate } from '../api/admin'
import { formatPrice } from './format'
import { ProductPicker } from './ProductPicker'

interface Props {
  itemId: number
  categoryId?: number | null
  onCurated: () => void // пересчитать вилку кита после изменений
}

// Курация flexible-позиции: исключение вариантов и ручное закрепление товаров.
export function CurationModal({ itemId, categoryId, onCurated }: Props) {
  const queryClient = useQueryClient()

  const preview = useQuery({
    queryKey: ['preview', itemId],
    queryFn: () => previewItem(itemId),
  })
  const candidates = useQuery({
    queryKey: ['candidates', itemId],
    queryFn: () => listCandidates(itemId),
  })

  const mutate = useMutation({
    mutationFn: (body: { product_id: number; is_pinned?: boolean; is_excluded?: boolean }) =>
      upsertCandidate(itemId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preview', itemId] })
      queryClient.invalidateQueries({ queryKey: ['candidates', itemId] })
      onCurated()
    },
  })

  if (preview.isLoading || candidates.isLoading || !preview.data || !candidates.data) {
    return <Loader />
  }

  const pinned = candidates.data.filter((c) => c.is_pinned)
  const excluded = candidates.data.filter((c) => c.is_excluded)

  return (
    <Stack>
      <Text fw={500}>Варианты по критериям ({preview.data.variants.length})</Text>
      {preview.data.variants.length === 0 ? (
        <Text c="dimmed" size="sm">
          Нет подходящих вариантов с ценой.
        </Text>
      ) : (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Товар</Table.Th>
              <Table.Th>Бренд</Table.Th>
              <Table.Th>Цена от</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {preview.data.variants.map((v) => (
              <Table.Tr key={v.product_id}>
                <Table.Td>{v.name}</Table.Td>
                <Table.Td>{v.brand ?? '—'}</Table.Td>
                <Table.Td>{formatPrice(v.min_price)}</Table.Td>
                <Table.Td>
                  <Button
                    size="xs"
                    variant="subtle"
                    color="red"
                    onClick={() => mutate.mutate({ product_id: v.product_id, is_excluded: true })}
                  >
                    Исключить
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Divider />
      <Text fw={500}>Закрепить товар вручную</Text>
      <ProductPicker
        categoryId={categoryId}
        placeholder="Найти товар для закрепления…"
        onSelect={(productId) => mutate.mutate({ product_id: productId, is_pinned: true })}
      />

      {(pinned.length > 0 || excluded.length > 0) && (
        <>
          <Divider />
          <Text fw={500}>Курация</Text>
          {pinned.map((c) => (
            <Group key={c.id} justify="space-between">
              <Group gap="xs">
                <Badge color="blue" variant="light">
                  закреплён
                </Badge>
                <Text size="sm">{c.product_name}</Text>
              </Group>
              <Button
                size="xs"
                variant="subtle"
                onClick={() => mutate.mutate({ product_id: c.product_id })}
              >
                Открепить
              </Button>
            </Group>
          ))}
          {excluded.map((c) => (
            <Group key={c.id} justify="space-between">
              <Group gap="xs">
                <Badge color="red" variant="light">
                  исключён
                </Badge>
                <Text size="sm">{c.product_name}</Text>
              </Group>
              <Button
                size="xs"
                variant="subtle"
                onClick={() => mutate.mutate({ product_id: c.product_id })}
              >
                Вернуть
              </Button>
            </Group>
          ))}
        </>
      )}
    </Stack>
  )
}
