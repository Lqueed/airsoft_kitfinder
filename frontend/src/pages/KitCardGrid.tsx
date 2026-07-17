import { Badge, Card, Group, SimpleGrid, Stack, Text } from '@mantine/core'
import { Link } from 'react-router-dom'

import type { KitCard } from '../api/types'
import { formatMinMax } from '../admin/format'

// Сетка карточек китов (каталог, визард, поиск).
export function KitCardGrid({ kits }: { kits: KitCard[] }) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
      {kits.map((kit) => (
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
  )
}
