import { Anchor, Button, Container, Group, Loader, Text, TextInput, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { searchKits } from '../api/public'
import { KitCardGrid } from './KitCardGrid'

// Поиск китов по названию и товарам состава (pg_trgm, с опечатками).
export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const [query, setQuery] = useState(q)

  const { data, isLoading } = useQuery({
    queryKey: ['search', q],
    queryFn: () => searchKits(q),
    enabled: q.trim().length >= 2,
  })

  return (
    <Container py="xl" size="lg">
      <Anchor component={Link} to="/" size="sm">
        ← В каталог
      </Anchor>
      <Title order={1} mt="sm" mb="md">
        Поиск китов
      </Title>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          setParams(query.trim().length >= 2 ? { q: query.trim() } : {})
        }}
      >
        <Group mb="lg">
          <TextInput
            placeholder="Название кита или товар из состава…"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            w={360}
            autoFocus
          />
          <Button type="submit" disabled={query.trim().length < 2}>
            Найти
          </Button>
        </Group>
      </form>

      {isLoading && <Loader />}
      {q.trim().length >= 2 && data && data.length === 0 && (
        <Text c="dimmed">По запросу «{q}» ничего не найдено.</Text>
      )}
      {data && data.length > 0 && <KitCardGrid kits={data} />}
    </Container>
  )
}
