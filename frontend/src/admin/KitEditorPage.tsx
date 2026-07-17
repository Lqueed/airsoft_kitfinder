import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Group,
  Loader,
  Modal,
  NumberInput,
  Paper,
  SegmentedControl,
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
import { useNavigate, useParams } from 'react-router-dom'

import {
  addItem,
  deleteItem,
  deleteKit,
  getKit,
  getMeta,
  publishKit,
  unpublishKit,
  updateKit,
  type ItemFields,
  type KitFields,
} from '../api/admin'
import { ApiError } from '../api/client'
import type { Kit, KitItemType, Meta } from '../api/types'
import { formatPrice, formatRange } from './format'
import { PreviewModal } from './PreviewModal'
import { ProductPicker } from './ProductPicker'

export function KitEditorPage() {
  const { id } = useParams()
  const kitId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: kit, isLoading } = useQuery({
    queryKey: ['kit', kitId],
    queryFn: () => getKit(kitId),
    enabled: Number.isFinite(kitId),
  })
  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: getMeta })

  const refresh = (updated: Kit) => {
    queryClient.setQueryData(['kit', kitId], updated)
    queryClient.invalidateQueries({ queryKey: ['kits'] })
  }

  if (isLoading || !kit) return <Loader m="xl" />

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{kit.name}</Title>
        <Group>
          <Badge color={kit.status === 'published' ? 'green' : 'gray'} size="lg">
            {kit.status === 'published' ? 'опубликован' : 'черновик'}
          </Badge>
          <Button variant="subtle" onClick={() => navigate('/admin')}>
            ← К списку
          </Button>
        </Group>
      </Group>

      <KitFieldsForm kit={kit} meta={meta} onSaved={refresh} />
      <PricingPanel kit={kit} onChanged={refresh} />
      <ItemsSection kit={kit} meta={meta} onChanged={refresh} />

      <Divider my="md" />
      <Button
        color="red"
        variant="light"
        w={200}
        onClick={async () => {
          if (confirm('Удалить кит?')) {
            await deleteKit(kit.id)
            queryClient.invalidateQueries({ queryKey: ['kits'] })
            navigate('/admin')
          }
        }}
      >
        Удалить кит
      </Button>
    </Stack>
  )
}

// --- Поля кита -------------------------------------------------------------

function KitFieldsForm({
  kit,
  meta,
  onSaved,
}: {
  kit: Kit
  meta: Meta | undefined
  onSaved: (k: Kit) => void
}) {
  const [fields, setFields] = useState<KitFields>({
    name: kit.name,
    description: kit.description ?? '',
    role: kit.role ?? null,
    drive_type: kit.drive_type ?? null,
    experience_level: kit.experience_level ?? null,
  })

  useEffect(() => {
    setFields({
      name: kit.name,
      description: kit.description ?? '',
      role: kit.role ?? null,
      drive_type: kit.drive_type ?? null,
      experience_level: kit.experience_level ?? null,
    })
  }, [kit])

  const mutation = useMutation({
    mutationFn: () => updateKit(kit.id, fields),
    onSuccess: onSaved,
  })

  return (
    <Paper withBorder p="md">
      <Stack>
        <TextInput
          label="Название"
          value={fields.name ?? ''}
          onChange={(e) => setFields((f) => ({ ...f, name: e.currentTarget.value }))}
        />
        <Textarea
          label="Описание"
          value={fields.description ?? ''}
          autosize
          minRows={2}
          onChange={(e) => setFields((f) => ({ ...f, description: e.currentTarget.value }))}
        />
        <Group grow>
          <Select
            label="Роль"
            clearable
            data={meta?.roles ?? []}
            value={fields.role ?? null}
            onChange={(v) => setFields((f) => ({ ...f, role: v }))}
          />
          <Select
            label="Тип привода"
            clearable
            data={meta?.drive_types ?? []}
            value={fields.drive_type ?? null}
            onChange={(v) => setFields((f) => ({ ...f, drive_type: v }))}
          />
          <Select
            label="Уровень"
            clearable
            data={meta?.experience_levels ?? []}
            value={fields.experience_level ?? null}
            onChange={(v) => setFields((f) => ({ ...f, experience_level: v }))}
          />
        </Group>
        <Button w={160} loading={mutation.isPending} onClick={() => mutation.mutate()}>
          Сохранить
        </Button>
      </Stack>
    </Paper>
  )
}

// --- Вилка цены + публикация ----------------------------------------------

function PricingPanel({ kit, onChanged }: { kit: Kit; onChanged: (k: Kit) => void }) {
  const publish = useMutation({ mutationFn: () => publishKit(kit.id), onSuccess: onChanged })
  const unpublish = useMutation({ mutationFn: () => unpublishKit(kit.id), onSuccess: onChanged })

  const conflict = publish.error instanceof ApiError && publish.error.status === 409

  return (
    <Paper withBorder p="md">
      <Group justify="space-between">
        <div>
          <Text size="sm" c="dimmed">
            Цена кита
          </Text>
          <Title order={3}>{formatRange(kit.pricing)}</Title>
        </div>
        <Group>
          {kit.status === 'draft' ? (
            <Button
              color="green"
              loading={publish.isPending}
              disabled={!kit.pricing.complete}
              onClick={() => publish.mutate()}
            >
              Опубликовать
            </Button>
          ) : (
            <Button
              variant="light"
              loading={unpublish.isPending}
              onClick={() => unpublish.mutate()}
            >
              Снять с публикации
            </Button>
          )}
        </Group>
      </Group>
      {conflict && (
        <Alert color="red" mt="sm">
          Нельзя опубликовать: у обязательной позиции нет доступной цены.
        </Alert>
      )}
      {!kit.pricing.complete && (
        <Alert color="yellow" mt="sm">
          Кит неполный — у одной из обязательных позиций нет активных офферов.
        </Alert>
      )}
    </Paper>
  )
}

// --- Позиции ---------------------------------------------------------------

function ItemsSection({
  kit,
  meta,
  onChanged,
}: {
  kit: Kit
  meta: Meta | undefined
  onChanged: (k: Kit) => void
}) {
  const [previewId, setPreviewId] = useState<number | null>(null)

  const remove = useMutation({
    mutationFn: (itemId: number) => deleteItem(itemId).then(() => getKit(kit.id)),
    onSuccess: onChanged,
  })

  return (
    <Paper withBorder p="md">
      <Title order={4} mb="sm">
        Позиции
      </Title>

      {kit.items.length === 0 && <Text c="dimmed">Позиций пока нет.</Text>}

      {kit.items.length > 0 && (
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Позиция</Table.Th>
              <Table.Th>Тип</Table.Th>
              <Table.Th>Обяз.</Table.Th>
              <Table.Th>Цена</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {kit.items.map((item) => {
              const pricing = kit.pricing.items.find((p) => p.item_id === item.id)
              return (
                <Table.Tr key={item.id}>
                  <Table.Td>{item.title}</Table.Td>
                  <Table.Td>{item.item_type === 'fixed' ? 'фикс.' : 'гибкая'}</Table.Td>
                  <Table.Td>{item.is_required ? 'да' : 'нет'}</Table.Td>
                  <Table.Td>
                    {pricing
                      ? pricing.min_price == null
                        ? '— (нет офферов)'
                        : `${formatPrice(pricing.min_price)} – ${formatPrice(pricing.max_price)}`
                      : '—'}
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs" justify="flex-end">
                      {item.item_type === 'flexible' && (
                        <Button size="xs" variant="light" onClick={() => setPreviewId(item.id)}>
                          Варианты ({pricing?.variant_count ?? 0})
                        </Button>
                      )}
                      <ActionIcon
                        color="red"
                        variant="subtle"
                        onClick={() => remove.mutate(item.id)}
                      >
                        ✕
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              )
            })}
          </Table.Tbody>
        </Table>
      )}

      <Divider my="md" />
      <AddItemForm kit={kit} meta={meta} onChanged={onChanged} />

      <Modal opened={previewId != null} onClose={() => setPreviewId(null)} title="Варианты позиции" size="lg">
        {previewId != null && <PreviewModal itemId={previewId} />}
      </Modal>
    </Paper>
  )
}

function AddItemForm({
  kit,
  meta,
  onChanged,
}: {
  kit: Kit
  meta: Meta | undefined
  onChanged: (k: Kit) => void
}) {
  const [type, setType] = useState<KitItemType>('fixed')
  const [title, setTitle] = useState('')
  const [required, setRequired] = useState(true)
  const [productId, setProductId] = useState<number | null>(null)
  const [categoryId, setCategoryId] = useState<string | null>(null)
  const [maxPrice, setMaxPrice] = useState<number | string>('')

  const reset = () => {
    setTitle('')
    setProductId(null)
    setCategoryId(null)
    setMaxPrice('')
    setRequired(true)
  }

  const mutation = useMutation({
    mutationFn: () => {
      const body: ItemFields = { item_type: type, title, is_required: required }
      if (type === 'fixed') body.product_id = productId
      else {
        body.category_id = categoryId ? Number(categoryId) : null
        body.max_price = maxPrice === '' ? null : Number(maxPrice)
      }
      return addItem(kit.id, body)
    },
    onSuccess: (updated) => {
      onChanged(updated)
      reset()
    },
  })

  const valid = title.trim() && (type === 'fixed' ? productId != null : categoryId != null)

  return (
    <Card withBorder>
      <Stack>
        <Text fw={500}>Добавить позицию</Text>
        <SegmentedControl
          value={type}
          onChange={(v) => setType(v as KitItemType)}
          data={[
            { label: 'Конкретный товар', value: 'fixed' },
            { label: 'Гибкая (категория)', value: 'flexible' },
          ]}
        />
        <TextInput
          label="Название позиции"
          placeholder="напр. Защита глаз"
          value={title}
          onChange={(e) => setTitle(e.currentTarget.value)}
        />
        {type === 'fixed' ? (
          <ProductPicker label="Товар" onSelect={setProductId} />
        ) : (
          <Group grow align="flex-end">
            <Select
              label="Категория"
              data={(meta?.categories ?? []).map((c) => ({ value: String(c.id), label: c.name }))}
              value={categoryId}
              onChange={setCategoryId}
              searchable
            />
            <NumberInput
              label="Макс. цена варианта (₽)"
              value={maxPrice}
              onChange={setMaxPrice}
              min={0}
              allowNegative={false}
            />
          </Group>
        )}
        <Checkbox
          label="Обязательная позиция"
          checked={required}
          onChange={(e) => setRequired(e.currentTarget.checked)}
        />
        <Button
          w={180}
          loading={mutation.isPending}
          disabled={!valid}
          onClick={() => mutation.mutate()}
        >
          Добавить
        </Button>
      </Stack>
    </Card>
  )
}
