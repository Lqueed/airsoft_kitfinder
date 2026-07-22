import {
  Anchor,
  Badge,
  Button,
  Divider,
  Group,
  Image,
  JsonInput,
  Loader,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { getMeta, getProduct, mergeProducts, unlinkOffer, updateProduct } from '../api/admin'
import type { ProductUpdate } from '../api/types'
import { formatPrice } from './format'
import { ProductPicker } from './ProductPicker'

interface Props {
  productId: number | null
  onClose: () => void
}

// Карточка товара: правка полей, офферы (отвязка/перепривязка), слияние дублей.
export function ProductDetailModal({ productId, onClose }: Props) {
  const queryClient = useQueryClient()
  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: getMeta })
  const { data: product, isLoading } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => getProduct(productId as number),
    enabled: productId != null,
  })

  const [form, setForm] = useState<ProductUpdate>({})
  const [attrsText, setAttrsText] = useState('{}')

  useEffect(() => {
    if (product) {
      setForm({
        name: product.name,
        brand: product.brand ?? '',
        category_id: product.category_id ?? null,
        description: product.description ?? '',
        image_url: product.image_url ?? '',
      })
      setAttrsText(JSON.stringify(product.attrs ?? {}, null, 2))
    }
  }, [product])

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['products'] })
    queryClient.invalidateQueries({ queryKey: ['product', productId] })
  }

  const save = useMutation({
    mutationFn: () => {
      let attrs: Record<string, unknown> | undefined
      try {
        attrs = JSON.parse(attrsText)
      } catch {
        attrs = undefined // невалидный JSON — не трогаем attrs
      }
      return updateProduct(productId as number, { ...form, attrs })
    },
    onSuccess: invalidate,
  })

  const unlink = useMutation({
    mutationFn: (offerId: number) => unlinkOffer(offerId),
    onSuccess: invalidate,
  })
  const merge = useMutation({
    mutationFn: (sourceId: number) => mergeProducts(productId as number, [sourceId]),
    onSuccess: invalidate,
  })

  const categoryOptions = (meta?.categories ?? []).map((c) => ({
    value: String(c.id),
    label: c.name,
  }))

  return (
    <Modal opened={productId != null} onClose={onClose} title="Товар" size="xl">
      {isLoading && <Loader />}
      {product && (
        <Stack>
          {form.image_url && (
            <Image
              src={form.image_url}
              w="100%"
              mah={320}
              fit="contain"
              radius="sm"
              alt={product.name}
            />
          )}
          <TextInput
            label="Название"
            value={form.name ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, name: e.currentTarget.value }))}
          />
          <Group grow>
            <TextInput
              label="Бренд"
              value={form.brand ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, brand: e.currentTarget.value }))}
            />
            <Select
              label="Категория"
              placeholder="—"
              clearable
              data={categoryOptions}
              value={form.category_id != null ? String(form.category_id) : null}
              onChange={(v) => setForm((f) => ({ ...f, category_id: v ? Number(v) : null }))}
            />
          </Group>
          <TextInput
            label="Картинка (URL)"
            value={form.image_url ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, image_url: e.currentTarget.value }))}
          />
          <Textarea
            label="Описание"
            autosize
            minRows={2}
            value={form.description ?? ''}
            onChange={(e) => setForm((f) => ({ ...f, description: e.currentTarget.value }))}
          />
          <JsonInput
            label="Атрибуты (attrs, JSON)"
            autosize
            minRows={3}
            validationError="Невалидный JSON"
            formatOnBlur
            value={attrsText}
            onChange={setAttrsText}
          />
          <Text size="xs" c="dimmed">
            slug: {product.slug} · match_key: {product.match_key} (не меняются)
          </Text>
          <Group>
            <Button onClick={() => save.mutate()} loading={save.isPending}>
              Сохранить
            </Button>
            {save.isError && <Text c="red">Ошибка сохранения</Text>}
          </Group>

          <Divider label="Офферы по магазинам" />
          {product.offers.length === 0 && <Text c="dimmed">Офферов нет.</Text>}
          {product.offers.length > 0 && (
            <Table verticalSpacing="xs" horizontalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Магазин</Table.Th>
                  <Table.Th>Название на сайте</Table.Th>
                  <Table.Th>Цена</Table.Th>
                  <Table.Th>Статус</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {product.offers.map((o) => (
                  <Table.Tr key={o.id}>
                    <Table.Td>
                      <Badge variant="light">{o.shop.name}</Badge>
                    </Table.Td>
                    <Table.Td>
                      <Anchor href={o.url} target="_blank" rel="noopener nofollow" size="sm">
                        {o.raw_title}
                      </Anchor>
                    </Table.Td>
                    <Table.Td>{formatPrice(o.price)}</Table.Td>
                    <Table.Td>
                      {!o.is_active && (
                        <Badge color="gray" size="xs">
                          снят
                        </Badge>
                      )}
                      {o.is_active && !o.in_stock && (
                        <Badge color="orange" size="xs">
                          нет в наличии
                        </Badge>
                      )}
                      {o.is_active && o.in_stock && (
                        <Badge color="green" size="xs">
                          в наличии
                        </Badge>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        onClick={() => unlink.mutate(o.id)}
                      >
                        Отвязать
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}

          <Divider label="Ручной матчинг" />
          <Stack gap="xs">
            <Title order={6}>Привязать оффер другого товара сюда</Title>
            <ProductPicker
              placeholder="Найти товар-дубль…"
              onSelect={(sourceId) => merge.mutate(sourceId)}
            />
            <Text size="xs" c="dimmed">
              Выбранный товар будет слит в этот: его офферы перевесятся сюда, дубль удалится.
            </Text>
            {merge.isError && <Text c="red">Ошибка слияния</Text>}
          </Stack>
        </Stack>
      )}
    </Modal>
  )
}
