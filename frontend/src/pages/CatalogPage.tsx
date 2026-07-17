import {
  Badge,
  Card,
  Container,
  Group,
  Loader,
  NumberInput,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { getMeta } from '../api/admin'
import { listKits } from '../api/public'
import { formatMinMax } from '../admin/format'

// Публичный каталог китов: фильтры (роль/привод/бюджет) хранятся в URL.
export function CatalogPage() {
  const [params, setParams] = useSearchParams()

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
      <Title order={1} mb="md">
        Каталог китов
      </Title>

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

      {data && data.items.length > 0 && (
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
          {data.items.map((kit) => (
            <Card
              key={kit.id}
              withBorder
              padding="lg"
              component={Link}
              to={`/kits/${kit.slug}`}
              style={{ textDecoration: 'none', color: 'inherit' }}
            >
              <Stack gap="xs">
                <Text fw={600}>{kit.name}</Text>
                <Group gap="xs">
                  {kit.role && <Badge variant="light">{kit.role}</Badge>}
                  {kit.drive_type && (
                    <Badge variant="light" color="grape">
                      {kit.drive_type}
                    </Badge>
                  )}
                </Group>
                <Text size="lg" fw={700}>
                  {formatMinMax(kit.price_min, kit.price_max, kit.complete)}
                </Text>
              </Stack>
            </Card>
          ))}
        </SimpleGrid>
      )}
    </Container>
  )
}
