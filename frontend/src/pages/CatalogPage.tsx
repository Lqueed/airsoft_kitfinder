import { useQuery } from '@tanstack/react-query'
import { Container, Loader, Text, Title } from '@mantine/core'

import { apiFetch } from '../api/client'

interface HealthResponse {
  status: string
}

// Заглушка каталога китов (M0): проверяет связь с бэкендом через health-чек.
export function CatalogPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<HealthResponse>('/health'),
  })

  return (
    <Container py="xl">
      <Title order={1}>airsoft_kitfinder</Title>
      <Text c="dimmed" mt="sm">
        Каталог китов появится здесь. Пока — проверка связи с бэкендом:
      </Text>
      {isLoading && <Loader mt="md" />}
      {isError && (
        <Text c="red" mt="md">
          Бэкенд недоступен
        </Text>
      )}
      {data && (
        <Text c="green" mt="md">
          Бэкенд отвечает: status={data.status}
        </Text>
      )}
    </Container>
  )
}
