import {
  Badge,
  Button,
  Checkbox,
  Group,
  Image,
  Loader,
  Modal,
  Pagination,
  Paper,
  Radio,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { bulkProducts, deleteProduct, getMeta, listProducts, mergeProducts } from '../api/admin'
import type { BulkAction, ProductSort } from '../api/types'
import { formatPrice } from './format'
import { ProductDetailModal } from './ProductDetailModal'

const PAGE_SIZE = 50
type BulkModal = 'merge' | 'category' | 'brand' | 'delete' | null

// Управление каноническими товарами: список с агрегатами, поиск/фильтры/сортировка,
// правка (модалка), ручной матчинг и массовые действия по чекбоксам.
export function ProductsPage() {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [categoryId, setCategoryId] = useState<string | null>(null)
  const [noCategory, setNoCategory] = useState(false)
  const [multishop, setMultishop] = useState(false)
  const [inStockOnly, setInStockOnly] = useState(true)
  const [sort, setSort] = useState<ProductSort>('name')
  const [order, setOrder] = useState<'asc' | 'desc'>('asc')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [detailId, setDetailId] = useState<number | null>(null)
  const [bulkModal, setBulkModal] = useState<BulkModal>(null)

  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: getMeta })

  const filters = {
    q: q.trim(),
    category_id: noCategory ? null : categoryId ? Number(categoryId) : null,
    no_category: noCategory,
    multishop,
    in_stock_only: inStockOnly,
    sort,
    order,
    page,
    page_size: PAGE_SIZE,
  }
  const { data, isLoading } = useQuery({
    queryKey: ['products', filters],
    queryFn: () => listProducts(filters),
  })

  const afterChange = () => {
    queryClient.invalidateQueries({ queryKey: ['products'] })
    setSelected(new Set())
    setBulkModal(null)
  }
  const bulk = useMutation({ mutationFn: (body: BulkAction) => bulkProducts(body), onSuccess: afterChange })
  const mergeSelected = useMutation({
    mutationFn: (targetId: number) =>
      mergeProducts(targetId, [...selected].filter((id) => id !== targetId)),
    onSuccess: afterChange,
  })
  const removeOne = useMutation({ mutationFn: (id: number) => deleteProduct(id), onSuccess: afterChange })

  const items = data?.items ?? []
  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  const toggle = (id: number) =>
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const allOnPage = items.length > 0 && items.every((p) => selected.has(p.id))
  const toggleAll = () =>
    setSelected((s) => {
      const next = new Set(s)
      if (allOnPage) items.forEach((p) => next.delete(p.id))
      else items.forEach((p) => next.add(p.id))
      return next
    })

  const setSortCol = (col: ProductSort) => {
    if (sort === col) setOrder((o) => (o === 'asc' ? 'desc' : 'asc'))
    else {
      setSort(col)
      setOrder('asc')
    }
    setPage(1)
  }
  const arrow = (col: ProductSort) => (sort === col ? (order === 'asc' ? ' ↑' : ' ↓') : '')

  return (
    <Stack>
      <Title order={2}>Товары</Title>

      <Group align="flex-end">
        <TextInput
          label="Поиск по названию"
          placeholder="напр. BLS 0.25"
          value={q}
          onChange={(e) => {
            setQ(e.currentTarget.value)
            setPage(1)
          }}
          w={260}
        />
        <Select
          label="Категория"
          placeholder="Все"
          clearable
          disabled={noCategory}
          w={200}
          data={(meta?.categories ?? []).map((c) => ({ value: String(c.id), label: c.name }))}
          value={categoryId}
          onChange={(v) => {
            setCategoryId(v)
            setPage(1)
          }}
        />
        <Checkbox
          label="Без категории"
          checked={noCategory}
          onChange={(e) => {
            setNoCategory(e.currentTarget.checked)
            setPage(1)
          }}
        />
        <Checkbox
          label="В >1 магазине"
          checked={multishop}
          onChange={(e) => {
            setMultishop(e.currentTarget.checked)
            setPage(1)
          }}
        />
        <Checkbox
          label="Только в наличии"
          checked={inStockOnly}
          onChange={(e) => {
            setInStockOnly(e.currentTarget.checked)
            setPage(1)
          }}
        />
      </Group>

      {selected.size > 0 && (
        <Paper withBorder p="sm" bg="var(--mantine-color-blue-light)">
          <Group>
            <Text fw={500}>Выбрано: {selected.size}</Text>
            <Button size="xs" onClick={() => setBulkModal('merge')} disabled={selected.size < 2}>
              Объединить
            </Button>
            <Button size="xs" variant="light" onClick={() => setBulkModal('category')}>
              Сменить категорию
            </Button>
            <Button size="xs" variant="light" onClick={() => setBulkModal('brand')}>
              Задать бренд
            </Button>
            <Button size="xs" color="red" variant="light" onClick={() => setBulkModal('delete')}>
              Удалить
            </Button>
            <Button size="xs" variant="subtle" onClick={() => setSelected(new Set())}>
              Снять выбор
            </Button>
          </Group>
        </Paper>
      )}

      {isLoading && <Loader />}
      {data && items.length === 0 && <Text c="dimmed">Ничего не найдено.</Text>}

      {items.length > 0 && (
        <>
          <Text size="sm" c="dimmed">
            Всего: {data?.total}
          </Text>
          <Table verticalSpacing="xs" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={36}>
                  <Checkbox checked={allOnPage} onChange={toggleAll} aria-label="Выбрать все" />
                </Table.Th>
                <Table.Th style={{ cursor: 'pointer' }} onClick={() => setSortCol('name')}>
                  Название{arrow('name')}
                </Table.Th>
                <Table.Th>Бренд</Table.Th>
                <Table.Th>Категория</Table.Th>
                <Table.Th style={{ cursor: 'pointer' }} onClick={() => setSortCol('offers')}>
                  Офферы{arrow('offers')}
                </Table.Th>
                <Table.Th>Магазины</Table.Th>
                <Table.Th style={{ cursor: 'pointer' }} onClick={() => setSortCol('price_min')}>
                  Цена{arrow('price_min')}
                </Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {items.map((p) => (
                <Table.Tr key={p.id}>
                  <Table.Td>
                    <Checkbox
                      checked={selected.has(p.id)}
                      onChange={() => toggle(p.id)}
                      aria-label={`Выбрать ${p.name}`}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Group gap="sm" wrap="nowrap">
                      {p.image_url && (
                        <Image
                          src={p.image_url}
                          w={40}
                          h={40}
                          fit="contain"
                          radius="sm"
                          alt={p.name}
                        />
                      )}
                      <span>{p.name}</span>
                    </Group>
                  </Table.Td>
                  <Table.Td>{p.brand ?? '—'}</Table.Td>
                  <Table.Td>
                    {p.category_name ? (
                      <Badge variant="light" size="sm">
                        {p.category_name}
                      </Badge>
                    ) : (
                      <Text c="dimmed" size="sm">
                        —
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>{p.offers_count}</Table.Td>
                  <Table.Td>{p.shops_count}</Table.Td>
                  <Table.Td>
                    {p.price_min == null
                      ? '—'
                      : `${formatPrice(p.price_min)} – ${formatPrice(p.price_max)}`}
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs" wrap="nowrap">
                      <Button size="compact-xs" variant="light" onClick={() => setDetailId(p.id)}>
                        Открыть
                      </Button>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        color="red"
                        onClick={() => removeOne.mutate(p.id)}
                      >
                        Удалить
                      </Button>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Group justify="center">
            <Pagination total={totalPages} value={page} onChange={setPage} />
          </Group>
        </>
      )}

      <ProductDetailModal productId={detailId} onClose={() => setDetailId(null)} />

      <BulkModals
        kind={bulkModal}
        selected={selected}
        items={items.map((p) => ({ id: p.id, name: p.name }))}
        categories={(meta?.categories ?? []).map((c) => ({ value: String(c.id), label: c.name }))}
        onClose={() => setBulkModal(null)}
        onMerge={(targetId) => mergeSelected.mutate(targetId)}
        onBulk={(body) => bulk.mutate(body)}
        pending={bulk.isPending || mergeSelected.isPending}
      />
    </Stack>
  )
}

// --- Модалки массовых действий ---------------------------------------------

interface BulkModalsProps {
  kind: BulkModal
  selected: Set<number>
  items: { id: number; name: string }[]
  categories: { value: string; label: string }[]
  onClose: () => void
  onMerge: (targetId: number) => void
  onBulk: (body: BulkAction) => void
  pending: boolean
}

function BulkModals({
  kind,
  selected,
  items,
  categories,
  onClose,
  onMerge,
  onBulk,
  pending,
}: BulkModalsProps) {
  const ids = [...selected]
  const [target, setTarget] = useState<string | null>(null)
  const [category, setCategory] = useState<string | null>(null)
  const [brand, setBrand] = useState('')

  const selectedNames = items.filter((i) => selected.has(i.id))

  return (
    <>
      <Modal opened={kind === 'merge'} onClose={onClose} title="Объединить товары">
        <Stack>
          <Text size="sm">
            Выберите товар-цель — остальные {ids.length - 1} вольются в него (офферы перевесятся,
            дубли удалятся).
          </Text>
          <Radio.Group value={target} onChange={setTarget}>
            <Stack gap="xs">
              {selectedNames.map((i) => (
                <Radio key={i.id} value={String(i.id)} label={i.name} />
              ))}
            </Stack>
          </Radio.Group>
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button
              disabled={!target}
              loading={pending}
              onClick={() => target && onMerge(Number(target))}
            >
              Объединить
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal opened={kind === 'category'} onClose={onClose} title="Сменить категорию">
        <Stack>
          <Select
            label="Категория"
            placeholder="Без категории"
            clearable
            data={categories}
            value={category}
            onChange={setCategory}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button
              loading={pending}
              onClick={() =>
                onBulk({
                  action: 'set_category',
                  product_ids: ids,
                  category_id: category ? Number(category) : null,
                })
              }
            >
              Применить к {ids.length}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal opened={kind === 'brand'} onClose={onClose} title="Задать бренд">
        <Stack>
          <TextInput
            label="Бренд"
            placeholder="напр. BLS"
            value={brand}
            onChange={(e) => setBrand(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button
              loading={pending}
              onClick={() =>
                onBulk({ action: 'set_brand', product_ids: ids, brand: brand.trim() || null })
              }
            >
              Применить к {ids.length}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal opened={kind === 'delete'} onClose={onClose} title="Удалить товары">
        <Stack>
          <Text size="sm">
            Удалить {ids.length} товаров? Офферы отвяжутся (не удалятся). Товары в fixed-позициях
            китов пропущены.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button
              color="red"
              loading={pending}
              onClick={() => onBulk({ action: 'delete', product_ids: ids })}
            >
              Удалить
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
