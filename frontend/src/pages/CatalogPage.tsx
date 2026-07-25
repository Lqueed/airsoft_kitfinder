import {
  Button,
  Container,
  Group,
  Loader,
  NumberInput,
  Select,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { getMeta } from '../api/admin'
import { listKits } from '../api/public'
import { KitCardGrid } from './KitCardGrid'

// Публичный каталог китов: фильтры (роль/привод/бюджет) хранятся в URL.
export function CatalogPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  const role = params.get('role') ?? undefined
  const driveType = params.get('drive_type') ?? undefined
  const budgetMin = params.get('budget_min')
  const budgetMax = params.get('budget_max')

  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: getMeta })

  const filters = {
    role,
    drive_type: driveType,
    budget_min: budgetMin ? Number(budgetMin) : undefined,
    budget_max: budgetMax ? Number(budgetMax) : undefined,
  }
  const { data, isLoading } = useQuery({
    queryKey: ['catalog', filters],
    queryFn: () => listKits(filters),
  })

  const setParam = (key: string, value: string | null) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      next.delete('page')
      return next
    })
  }

  return (
    <Container py="xl" size="lg">
      <Group justify="space-between" mb="md">
        <Title order={1}>Каталог китов</Title>
        <Group gap="xs">
          <Button component={Link} to="/products" variant="subtle">
            Сравнить цены на товары
          </Button>
          <Button component={Link} to="/wizard" variant="light">
            Подобрать кит →
          </Button>
        </Group>
      </Group>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (query.trim().length >= 2) navigate(`/search?q=${encodeURIComponent(query.trim())}`)
        }}
      >
        <Group mb="lg">
          <TextInput
            placeholder="Поиск по названию или товару из состава…"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            w={360}
          />
          <Button type="submit" disabled={query.trim().length < 2}>
            Найти
          </Button>
        </Group>
      </form>

      <Group align="flex-end" mb="lg">
        <Select
          label="Роль"
          placeholder="Любая"
          clearable
          w={180}
          data={meta?.roles ?? []}
          value={role ?? null}
          onChange={(v) => setParam('role', v)}
        />
        <Select
          label="Тип привода"
          placeholder="Любой"
          clearable
          w={180}
          data={meta?.drive_types ?? []}
          value={driveType ?? null}
          onChange={(v) => setParam('drive_type', v)}
        />
        <NumberInput
          label="Бюджет от, ₽"
          w={140}
          min={0}
          allowNegative={false}
          value={budgetMin ? Number(budgetMin) : ''}
          onChange={(v) => setParam('budget_min', v === '' ? null : String(v))}
        />
        <NumberInput
          label="Бюджет до, ₽"
          w={140}
          min={0}
          allowNegative={false}
          value={budgetMax ? Number(budgetMax) : ''}
          onChange={(v) => setParam('budget_max', v === '' ? null : String(v))}
        />
      </Group>

      {isLoading && <Loader />}
      {data && data.items.length === 0 && (
        <Text c="dimmed">Под фильтры ничего не подошло.</Text>
      )}
      {data && data.items.length > 0 && <KitCardGrid kits={data.items} />}
    </Container>
  )
}
